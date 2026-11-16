"""Yüz ifadesi modeli eğitimi: FER2013 + FER+ → timm omurgası → kalibre edilmiş ONNX.

Örnek (Kaggle GPU):
    python train.py --fer2013 /kaggle/input/fer2013/fer2013.csv --model convnext_tiny.fb_in22k --epochs 35

Çıktılar (`--out` klasörü):
    best.pt · emotion.onnx · emotion.json (backend'in okuduğu tanım) · metrics.json · confusion.png · history.csv
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import random
import time
from pathlib import Path

import numpy as np
import pandas as pd
import timm
import torch
import torch.nn.functional as F
from sklearn.metrics import confusion_matrix, f1_score
from torch import nn
from torch.utils.data import DataLoader
from torchvision.transforms import v2

from ferplus import FERPLUS_URL, LABELS, FerPlusDataset, load_ferplus

MEAN, STD = 0.5, 0.5


# --------------------------------------------------------------------------------------- veri
def make_transforms(size: int, train: bool) -> v2.Compose:
    common_tail = [
        v2.ToDtype(torch.float32, scale=True),
        v2.Lambda(lambda x: x.expand(3, -1, -1)),
        v2.Normalize([MEAN] * 3, [STD] * 3),
    ]
    if not train:
        return v2.Compose([v2.Resize(size, antialias=True), *common_tail])
    return v2.Compose(
        [
            v2.RandomResizedCrop(size, scale=(0.75, 1.0), ratio=(0.9, 1.1), antialias=True),
            v2.RandomHorizontalFlip(),
            v2.RandomApply([v2.RandomAffine(degrees=15, translate=(0.05, 0.05))], p=0.7),
            v2.RandomApply([v2.ColorJitter(brightness=0.35, contrast=0.35)], p=0.8),
            v2.RandomApply([v2.GaussianBlur(3, sigma=(0.1, 1.2))], p=0.2),
            *common_tail,
            v2.RandomErasing(p=0.25, scale=(0.02, 0.15)),
        ]
    )


# --------------------------------------------------------------------------------------- kayıp
def soft_cross_entropy(
    logits: torch.Tensor, target: torch.Tensor, smoothing: float = 0.0, weight: torch.Tensor | None = None
) -> torch.Tensor:
    if smoothing:
        target = target * (1 - smoothing) + smoothing / target.shape[1]
    logp = F.log_softmax(logits, dim=1)
    if weight is not None:
        logp = logp * weight
    return -(target * logp).sum(1).mean()


def mixup(x: torch.Tensor, y: torch.Tensor, alpha: float) -> tuple[torch.Tensor, torch.Tensor]:
    lam = float(np.random.beta(alpha, alpha))
    idx = torch.randperm(x.size(0), device=x.device)
    return lam * x + (1 - lam) * x[idx], lam * y + (1 - lam) * y[idx]


# --------------------------------------------------------------------------------------- değerlendirme
@torch.no_grad()
def predict(
    model: nn.Module, loader: DataLoader, device: torch.device, tta: bool = True
) -> tuple[torch.Tensor, torch.Tensor]:
    model.eval()
    logits, targets = [], []
    for x, y in loader:
        x = x.to(device, non_blocking=True)
        with torch.autocast(device.type, enabled=device.type == "cuda"):
            out = model(x)
            if tta:
                out = (out + model(torch.flip(x, dims=[3]))) / 2
        logits.append(out.float().cpu())
        targets.append(y)
    return torch.cat(logits), torch.cat(targets)


def expected_calibration_error(probs: np.ndarray, labels: np.ndarray, bins: int = 15) -> float:
    conf, pred = probs.max(1), probs.argmax(1)
    edges = np.linspace(0, 1, bins + 1)
    ece = 0.0
    for lo, hi in itertools.pairwise(edges):
        m = (conf > lo) & (conf <= hi)
        if m.any():
            ece += m.mean() * abs((pred[m] == labels[m]).mean() - conf[m].mean())
    return float(ece)


def metrics(logits: torch.Tensor, targets: torch.Tensor, temperature: float = 1.0) -> dict[str, float]:
    probs = F.softmax(logits / temperature, 1).numpy()
    y = targets.argmax(1).numpy()
    pred = probs.argmax(1)
    return {
        "accuracy": float((pred == y).mean()),
        "macro_f1": float(f1_score(y, pred, average="macro")),
        "nll": float(F.cross_entropy(logits / temperature, torch.from_numpy(y)).item()),
        "ece": expected_calibration_error(probs, y),
    }


def fit_temperature(logits: torch.Tensor, targets: torch.Tensor) -> float:
    """Guo ve ark. (2017) sıcaklık ölçekleme: doğrulama NLL'ini en aza indiren T."""
    y = targets.argmax(1)
    log_t = torch.zeros(1, requires_grad=True)
    opt = torch.optim.LBFGS([log_t], lr=0.1, max_iter=200)

    def closure() -> torch.Tensor:
        opt.zero_grad()
        loss = F.cross_entropy(logits / log_t.exp(), y)
        loss.backward()
        return loss

    opt.step(closure)
    return float(log_t.exp().item())


def save_confusion(logits: torch.Tensor, targets: torch.Tensor, path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    cm = confusion_matrix(
        targets.argmax(1).numpy(), logits.argmax(1).numpy(), labels=range(len(LABELS)), normalize="true"
    )
    fig, ax = plt.subplots(figsize=(7.5, 6.5), dpi=150)
    im = ax.imshow(cm, cmap="Blues", vmin=0, vmax=1)
    ax.set_xticks(range(len(LABELS)), LABELS, rotation=40, ha="right")
    ax.set_yticks(range(len(LABELS)), LABELS)
    ax.set_xlabel("Tahmin")
    ax.set_ylabel("Gerçek (FER+ çoğunluk)")
    for i in range(len(LABELS)):
        for j in range(len(LABELS)):
            ax.text(
                j,
                i,
                f"{cm[i, j]:.2f}",
                ha="center",
                va="center",
                fontsize=8,
                color="white" if cm[i, j] > 0.5 else "#1f2937",
            )
    fig.colorbar(im, fraction=0.046)
    ax.set_title("FER+ test — normalize karışıklık matrisi")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


# --------------------------------------------------------------------------------------- dışa aktarım
def export_onnx(model: nn.Module, size: int, out: Path, temperature: float, info: dict) -> None:
    import onnxruntime as ort

    model = model.eval().cpu().float()
    dummy = torch.randn(2, 3, size, size)
    onnx_path = out / "emotion.onnx"
    export_kwargs = {
        "input_names": ["input"],
        "output_names": ["logits"],
        "dynamic_axes": {"input": {0: "batch"}, "logits": {0: "batch"}},
        "opset_version": 17,
    }
    try:  # PyTorch ≥ 2.5: klasik (TorchScript) dışa aktarıcıyı açıkça seç
        torch.onnx.export(model, dummy, onnx_path, dynamo=False, **export_kwargs)
    except TypeError:  # daha eski sürümlerde `dynamo` parametresi yok
        torch.onnx.export(model, dummy, onnx_path, **export_kwargs)
    sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    with torch.no_grad():
        ref = model(dummy).numpy()
    diff = float(np.abs(sess.run(None, {"input": dummy.numpy()})[0] - ref).max())
    if diff > 1e-3:
        raise RuntimeError(f"ONNX çıktısı PyTorch'tan sapıyor: {diff}")
    meta = {
        "name": info["name"],
        "labels": LABELS,
        "input_size": size,
        "channels": 3,
        "mean": [MEAN] * 3,
        "std": [STD] * 3,
        "scale": 255.0,
        "source_size": 48,
        "temperature": round(temperature, 4),
        "metrics": info["test"],
        "trained_on": "FER2013 + FER+ (MIT)",
        "onnx_max_abs_diff": diff,
    }
    (out / "emotion.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), "utf-8")
    print(f"ONNX hazır: {onnx_path} (PyTorch farkı {diff:.2e})")


# --------------------------------------------------------------------------------------- ana akış
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fer2013", type=Path, required=True, help="fer2013.csv yolu")
    ap.add_argument("--ferplus", default=FERPLUS_URL, help="fer2013new.csv yolu veya URL")
    ap.add_argument("--model", default="convnext_tiny.fb_in22k")
    ap.add_argument("--size", type=int, default=112)
    ap.add_argument("--epochs", type=int, default=35)
    ap.add_argument("--batch", type=int, default=128)
    ap.add_argument("--lr", type=float, default=4e-4)
    ap.add_argument("--wd", type=float, default=0.05)
    ap.add_argument("--warmup", type=int, default=2)
    ap.add_argument("--smoothing", type=float, default=0.05)
    ap.add_argument("--mixup", type=float, default=0.2, help="0 = kapalı")
    ap.add_argument("--mixup-prob", type=float, default=0.3)
    ap.add_argument("--drop-path", type=float, default=0.1)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--limit", type=int, default=0, help="duman testi için örnek sınırı")
    ap.add_argument("--no-pretrained", action="store_true")
    ap.add_argument("--out", type=Path, default=Path("artifacts") / time.strftime("%Y%m%d-%H%M%S"))
    args = ap.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    args.out.mkdir(parents=True, exist_ok=True)
    print(f"Cihaz: {device} · çıktı: {args.out}")

    table = load_ferplus(args.fer2013, args.ferplus)
    if args.limit:
        table = table.groupby("split", group_keys=False).head(args.limit)
    print(table["split"].value_counts().to_dict())

    sets = {s: FerPlusDataset(table, s, make_transforms(args.size, s == "train")) for s in ("train", "val", "test")}
    loaders = {
        s: DataLoader(
            d,
            batch_size=args.batch,
            shuffle=s == "train",
            num_workers=args.workers,
            pin_memory=device.type == "cuda",
            drop_last=s == "train" and len(d) > args.batch,
        )
        for s, d in sets.items()
    }

    # Az görülen sınıflar için ılımlı ağırlık (ters frekansın karekökü)
    freq = sets["train"].targets.sum(0)
    class_w = (freq.sum() / (len(LABELS) * freq.clamp(min=1))).sqrt()
    class_w = (class_w / class_w.mean()).to(device)
    print("Sınıf ağırlıkları:", dict(zip(LABELS, class_w.cpu().numpy().round(2), strict=True)))

    model = timm.create_model(
        args.model, pretrained=not args.no_pretrained, num_classes=len(LABELS), drop_path_rate=args.drop_path
    ).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.wd)
    steps = args.epochs * len(loaders["train"])
    warm = args.warmup * len(loaders["train"])
    sched = torch.optim.lr_scheduler.LambdaLR(
        opt,
        lambda s: (
            (s + 1) / max(1, warm) if s < warm else 0.5 * (1 + math.cos(math.pi * (s - warm) / max(1, steps - warm)))
        ),
    )
    scaler = torch.amp.GradScaler(enabled=device.type == "cuda")

    best, history = -1.0, []
    for epoch in range(1, args.epochs + 1):
        model.train()
        t0, run_loss, n = time.time(), 0.0, 0
        for x, y in loaders["train"]:
            x, y = x.to(device, non_blocking=True), y.to(device, non_blocking=True)
            if args.mixup and random.random() < args.mixup_prob:
                x, y = mixup(x, y, args.mixup)
            with torch.autocast(device.type, enabled=device.type == "cuda"):
                loss = soft_cross_entropy(model(x), y, args.smoothing, class_w)
            opt.zero_grad(set_to_none=True)
            scaler.scale(loss).backward()
            scaler.unscale_(opt)
            nn.utils.clip_grad_norm_(model.parameters(), 2.0)
            scaler.step(opt)
            scaler.update()
            sched.step()
            run_loss += loss.item() * len(x)
            n += len(x)

        val = metrics(*predict(model, loaders["val"], device))
        row = {
            "epoch": epoch,
            "train_loss": run_loss / max(n, 1),
            **{f"val_{k}": v for k, v in val.items()},
            "lr": opt.param_groups[0]["lr"],
            "sec": time.time() - t0,
        }
        history.append(row)
        flag = ""
        if val["accuracy"] > best:
            best = val["accuracy"]
            torch.save(
                {"model": model.state_dict(), "args": {k: str(v) for k, v in vars(args).items()}}, args.out / "best.pt"
            )
            flag = " ★"
        print(
            f"[{epoch:02d}/{args.epochs}] loss {row['train_loss']:.4f} · val acc {val['accuracy']:.4f} "
            f"· F1 {val['macro_f1']:.4f} · {row['sec']:.0f}s{flag}"
        )
        pd.DataFrame(history).to_csv(args.out / "history.csv", index=False)

    model.load_state_dict(torch.load(args.out / "best.pt", map_location=device)["model"])
    val_logits, val_t = predict(model, loaders["val"], device)
    temperature = fit_temperature(val_logits, val_t)
    test_logits, test_t = predict(model, loaders["test"], device)
    result = {
        "name": f"vibesight-{args.model.split('.')[0]}-ferplus",
        "model": args.model,
        "temperature": temperature,
        "val": metrics(val_logits, val_t, temperature),
        "test_uncalibrated": metrics(test_logits, test_t),
        "test": metrics(test_logits, test_t, temperature),
        "per_class_recall": dict(
            zip(
                LABELS,
                confusion_matrix(test_t.argmax(1), test_logits.argmax(1), labels=range(len(LABELS)), normalize="true")
                .diagonal()
                .round(4)
                .tolist(),
                strict=True,
            )
        ),
        "counts": {s: len(d) for s, d in sets.items()},
    }
    (args.out / "metrics.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), "utf-8")
    save_confusion(test_logits, test_t, args.out / "confusion.png")
    print(json.dumps(result["test"], indent=2))
    export_onnx(model, args.size, args.out, temperature, result)


if __name__ == "__main__":
    main()
