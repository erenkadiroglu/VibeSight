# İfade modeli eğitimi

## Kaggle'da (önerilen, ücretsiz GPU)
1. kaggle.com'da hesap açın ve **telefon doğrulaması** yapın (GPU ve internet erişimi için gerekli).
2. *Create → New Notebook → File → Import Notebook* ile `training/notebooks/kaggle_train_emotion.ipynb` dosyasını yükleyin.
3. Sağ panelde: **Accelerator: GPU T4 x2**, **Internet: On**.
4. **+ Add Input** → `deadskull7/fer2013` veri setini ekleyin.
5. İlk hücredeki `REPO_URL` repoyu gösterir (fork kullanıyorsanız kendi adresinizle değiştirin).
6. Sağ üstte **Save Version → Save & Run All (Commit)**. Arka planda çalışır; bittiğinde defter sayfasının **Output** sekmesinden `vibesight-emotion.zip` dosyasını indirin.
7. Zip içindeki `emotion.onnx` ve `emotion.json` dosyalarını `backend/models/` klasörüne kopyalayın.

## Yerelde (NVIDIA GPU varsa)
```bash
cd training && uv venv && uv pip install -r requirements.txt
```

```bash
uv run python train.py --fer2013 data/fer2013.csv --epochs 35
```

FER+ etiketleri (`fer2013new.csv`) çalışma sırasında Microsoft'un GitHub reposundan otomatik indirilir.

## Duman testi (GPU'suz, 1 dakika)
Hat uçtan uca çalışıyor mu diye görmek için:
```bash
uv run python train.py --fer2013 data/fer2013.csv --model resnet18 --no-pretrained --epochs 1 --limit 256 --size 64 --workers 0
```

## Çıktılar
| Dosya | İçerik |
|---|---|
| `emotion.onnx` | Dinamik batch'li model |
| `emotion.json` | Etiketler, ön işleme, kalibrasyon sıcaklığı, test metrikleri |
| `metrics.json` | Doğruluk, macro-F1, NLL, ECE, sınıf bazında recall |
| `confusion.png` | Normalize karışıklık matrisi |
| `history.csv` | Epoch bazında eğitim geçmişi |

Sonuçları `docs/MODEL_CARD.md` dosyasına işleyin.
