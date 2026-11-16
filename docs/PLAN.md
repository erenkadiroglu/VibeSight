# VibeSight — Proje Planı

> Gerçek zamanlı sınıf / oda atmosferi analizi: kişi sayımı, yüz ifadesi, enerji ve dikkat göstergeleri.
> Donanım: TP-Link Tapo C200 (RTSP) · Çalışma: tamamen yerel (bulut yok, görüntü kaydı yok).

---

## 0. Kapsam ve dürüst sınırlar

| İstenen | Ne ölçeriz | Nasıl adlandırırız (arayüzde) |
|---|---|---|
| İnsan sayısı | Kişi tespiti + takip | **Kişi sayısı** |
| Duygular | Yüz **ifadesi** sınıflandırması (8 sınıf, FER+) | **Gözlenen ifade** |
| Enerji seviyesi | Uyarılmışlık (arousal) + göz kapanma (PERCLOS) + esneme + hareket | **Enerji endeksi (0–100)** |
| Psikolojik durum | Yukarıdakilerin birleşiminden oda düzeyinde atmosfer | **Atmosfer** (Odaklı / Pozitif / Yorgun / Gergin / Sakin) |

**Neden bu adlandırma?** Bilimsel literatür (Barrett ve ark., 2019, *Psychological Science in the Public Interest*)
yüz ifadesinin iç duygu durumunu güvenilir biçimde göstermediğini ortaya koyuyor. Bir kameranın "psikolojik durum"
teşhis ettiğini iddia etmek hem yanlış hem de hukuken risklidir. Biz **gözlenebilir sinyalleri** ölçüp
**oda düzeyinde, anonim ve toplu** gösteriyoruz. Bu, projeyi hem daha dürüst hem de daha savunulabilir yapar.

### Hukuki çerçeve (mutlaka okuyun: `docs/ETHICS_KVKK.md`)
- **KVKK (Türkiye):** Yüz görüntüsünden çıkarılan veriler biyometrik veri sayılabilir → *özel nitelikli kişisel veri*.
  Katılımcılardan **açık rıza**, aydınlatma metni ve görünür bilgilendirme gerekir.
- **AB Yapay Zekâ Yasası, Md. 5(1)(f):** İşyeri ve **eğitim kurumlarında** duygu tanıma sistemlerinin kullanımı
  2 Şubat 2025'ten itibaren yasaktır (tıbbi/güvenlik istisnaları hariç). AB'de gerçek bir sınıfta kullanılamaz.
- **Tasarım kararlarımız:** görüntü/yüz **asla diske yazılmaz**, kimlik tanıma **yok**, takip ID'leri geçicidir,
  yalnızca **oda düzeyindeki toplu metrikler** saklanır, arayüzde "gizlilik modu" (yüzleri bulanıklaştırma) vardır.
  Proje bir **akademik demo / araştırma prototipi** olarak konumlanır.

---

## 1. Mimari

```
Tapo C200 ──RTSP(stream1/stream2)──► [Kaynak katmanı]  (OpenCV, otomatik yeniden bağlanma, son-kare tamponu)
                                          │
                                          ▼
                                 [Analiz hattı ~5 Hz]
     ┌───────────────┬─────────────────────┼─────────────────────┬───────────────────┐
     ▼               ▼                     ▼                     ▼                   ▼
 Kişi tespiti     Takip (IoU)        Yüz + 478 nokta        İfade sınıflandırıcı   Hareket enerjisi
 YOLOX-S ONNX     geçici ID          MediaPipe Landmarker   ONNX (FER+ 8 sınıf)    kare farkı / kişi
                                     + blendshape (göz,      (kendi modelimiz)
                                       çene) + baş pozu
     └───────────────┴─────────────────────┼─────────────────────┴───────────────────┘
                                          ▼
                          [Kişi başı durum: EMA ile yumuşatma]
                                          ▼
                [Oda toplayıcısı: sayı, ifade dağılımı, valans/arousal, enerji, dikkat, atmosfer]
                     │                                   │
                     ▼                                   ▼
          SQLite (yalnızca toplu zaman serisi)    WebSocket (JSON + JPEG, aynı mesajda → senkron overlay)
                                                         ▼
                                       React + TypeScript gösterge paneli (canlı)
```

**Neden bu yığın?**
- **Çalışma zamanında PyTorch yok:** her şey ONNX Runtime + MediaPipe → sıradan bir dizüstü bilgisayarın CPU'sunda çalışır.
- **Lisanslar temiz:** YOLOX (Apache-2.0), MediaPipe (Apache-2.0), kendi modelimiz (MIT), FER+ etiketleri (MIT).
  Ultralytics YOLO AGPL-3.0 olduğu için bilinçli olarak tercih edilmedi.
- **Görüntü ve metrik aynı WebSocket mesajında** → kutular görüntüyle birebir hizalı.

### Klasör yapısı
```
vibesight/
├─ backend/            FastAPI + analiz hattı (Python 3.12, uv)
│  ├─ vibesight/
│  │  ├─ sources/      rtsp / webcam / video dosyası
│  │  ├─ vision/       detector, tracker, face, emotion, motion
│  │  ├─ analytics/    affect (circumplex), aggregator, atmosphere
│  │  ├─ storage/      SQLite zaman serisi
│  │  └─ api/          REST + WebSocket
│  ├─ models/          indirilen/eğitilen ONNX modelleri (git'e girmez)
│  └─ tests/
├─ training/           İfade modeli eğitimi (Kaggle GPU defteri + betikler)
├─ frontend/           React + Vite + TS + Tailwind gösterge paneli
├─ docs/               PLAN, CAMERA_SETUP, DATASETS, MODEL_CARD, ETHICS_KVKK
├─ scripts/            model indirme, kontrol, geliştirme yardımcıları
└─ Makefile            tek komutla kurulum / test / çalıştırma (CI'a bağımlı değil)
```

---

## 2. Makine öğrenmesi planı

### 2.1 Kişi sayımı
- **Model:** YOLOX-S (COCO, mAP 40.5), yalnızca `person` sınıfı. 640×640, ONNX, CPU'da ~60–90 ms.
- **Takip:** IoU + merkez mesafesi tabanlı hafif takipçi (bağımlılıksız), 1.5 sn tolerans → sayı titremez.
- **Sayı = medyan(son 2 sn)**, ani sıçramaları bastırır.
- **Doğrulama:** kendi çekeceğimiz 3–5 dakikalık sınıf videosunda elle sayım ile MAE (hedef: MAE < 0.5 kişi).

### 2.2 Yüz ifadesi (eğitim yapacağımız asıl model)
**Veri setleri (hepsi ücretsiz ve akademik olarak yerleşik):**

| Veri seti | Boyut | Lisans / erişim | Rol |
|---|---|---|---|
| **FER2013** (Kaggle) | 35.887 gri 48×48 | Kaggle, araştırma amaçlı, anında indirme | Görüntü kaynağı |
| **FER+** (Microsoft) | FER2013 için 10 kişilik oylama etiketleri | **MIT**, GitHub | **Ana etiketler** (çok daha temiz) |
| RAF-DB (opsiyonel) | 15.339 renkli, gerçek dünya | Ücretsiz, akademik e-posta ile talep | Alan genellemesi |
| AffectNet (opsiyonel) | ~290k + valans/arousal | Ücretsiz, akademik başvuru | Faz 2: doğrudan valans/arousal |

Varsayılan yol yalnızca **FER2013 + FER+** ile başvuru beklemeden tamamlanır. RAF-DB/AffectNet onay gelirse eklenir.

**Sınıflar (FER+ 8):** nötr, mutlu, şaşkın, üzgün, kızgın, iğrenmiş, korkmuş, küçümseyen.

**Model ve eğitim:**
- Omurga: `convnext_tiny` veya `efficientnet_b0` (timm, ImageNet ön-eğitimli), giriş 112×112 (gri → 3 kanal).
- Kayıp: FER+ oy dağılımına karşı **soft-label cross-entropy** (makalede en iyi sonucu veren "probabilistic" yaklaşım) + label smoothing.
- Augmentasyon: RandomResizedCrop, yatay çevirme, ±15° döndürme, parlaklık/kontrast, RandomErasing, MixUp/CutMix (düşük oran).
- Optimizasyon: AdamW, cosine LR + warmup, AMP, 30–40 epoch, en iyi model doğrulama doğruluğuna göre.
- Dengesizlik: sınıf ağırlıkları / balanced sampler (iğrenme ve küçümseme çok az).
- **Değerlendirme:** FER+ resmi test bölümü; accuracy, **macro-F1**, karışıklık matrisi, sınıf başına recall, ECE (kalibrasyon).
  Hedef: test doğruluğu **≥ %85**, macro-F1 ≥ 0.65.
- **Kalibrasyon:** temperature scaling → olasılıklar arayüzde güvenle kullanılabilir.
- **Dışa aktarım:** ONNX (opset 17) + onnxruntime ile PyTorch çıktısı eşitlik testi (max fark < 1e-4), isteğe bağlı INT8 kuantizasyon.
- **Ortam:** Kaggle Notebooks (ücretsiz GPU, haftalık ~30 saat; FER2013 Kaggle'da hazır). Defter `training/notebooks/` altında.
- **Canlı test sonucu ve karar (güncelleme):** FER+ modeli webcam'de zayıf kaldı (48×48 gri eğitim verisi ile gerçek
  görüntü arasındaki alan farkı). Varsayılan ifade modeli **EmotiEffLib `enet_b0_8_va_mtl`** (AffectNet, Apache-2.0)
  oldu; gerekçe `docs/DATASETS.md`. Kendi modelimiz `VIBESIGHT_EMOTION_MODEL=emotion.onnx` ile seçilebilir.

### 2.3 Enerji ve dikkat (eğitimsiz, literatüre dayalı sinyaller)
| Sinyal | Kaynak | Literatür |
|---|---|---|
| Göz kapanma oranı, **PERCLOS** | MediaPipe blendshape `eyeBlink*` | Wierwille 1994; Dinges & Grace 1998 |
| Esneme | blendshape `jawOpen` + süre eşiği | — |
| Baş pozu (yaw/pitch) | yüz dönüşüm matrisi | Dikkat yönü vekili |
| Hareket enerjisi | kişi kutusu içinde kare farkı | Aktivite vekili |
| Valans / Uyarılmışlık | ifade olasılıkları × Russell circumplex koordinatları | Russell 1980 |

**Enerji endeksi** = 100 × (0.25 + 0.75 · canlılık) × uyanıklık × (esneme varsa 0.8)
- canlılık = 0.6 · uyarılmışlık' + 0.4 · hareket' · uyanıklık = 1 − min(PERCLOS / 0.4, 1)
- Ayar noktaları: hareketsiz-nötr-uyanık ≈ 47 (Orta), gülümseyen-hareketli ≥ 65 (Yüksek), gözleri sık kapanan < 15.
- (İlk sürümdeki toplamsal formül, uyanık oturan herkese 65+ veriyordu; canlı testte düzeltildi.)
**Katılım** = öğrenilmiş model (EmotiEffLib, EngageWild): kişi başına son 128 karenin yüz öznitelikleri → dikkat ağı → katılımcı olasılığı. Baş açısından gelen "öne dönük" oranı ayrı bir sinyal olarak kalır.
**Atmosfer** = kural tabanlı birleşim (ör. yüksek enerji + pozitif valans → "Pozitif & Enerjik"; düşük enerji + yüksek PERCLOS → "Yorgun").
Ağırlıklar `config` dosyasında; Faz 2'de DAiSEE (ücretsiz, akademik talep) ile öğrenilmiş bir "katılım" modeline geçilebilir.

### 2.4 Kamera gerçekleri
- C200: 1080p, ~110° yatay görüş. Güvenilir ifade için yüz **≥ 48 px** olmalı → yaklaşık **≤ 4–5 m** mesafe.
- Büyük sınıfta: sayım tüm sınıfta çalışır; ifade/enerji yalnızca yeterince büyük yüzler için hesaplanır ve
  arayüz "analiz edilen yüz: 12/25" şeklinde kapsamı **dürüstçe** gösterir.

---

## 3. Arayüz planı
- **Teknoloji:** React 19 + Vite + TypeScript + Tailwind CSS v4, ikonlar `lucide-react`, grafikler hafif SVG bileşenleri.
- **Ekran düzeni:** solda canlı görüntü (kutular, ID, baskın ifade, gizlilik modu), sağda KPI kartları
  (kişi sayısı, enerji, dikkat, atmosfer), altta zaman serileri (son 10 dk) ve ifade dağılımı, valans–arousal düzlemi.
- **Detaylar:** koyu/açık tema, Türkçe arayüz, bağlantı durumu göstergesi, FPS/gecikme, boş/hata durumları,
  klavye erişilebilirliği, WCAG AA kontrast, renk körlüğüne uygun palet, ekran boyutuna duyarlı yerleşim.

---

## 4. Yol haritası

| Faz | İçerik | Kabul kriteri |
|---|---|---|
| **F0** Temel | Repo, araçlar, dokümanlar, Makefile, pre-commit | `make check` yeşil |
| **F1** Hat | Kaynaklar, tespit, takip, yüz, hareket, toplayıcı, API/WS | Webcam/videoda canlı metrik |
| **F2** Arayüz | Gösterge paneli | Görsel inceleme + erişilebilirlik kontrolü |
| **F3** Eğitim | FER+ hazırlık, eğitim, değerlendirme, ONNX | Test ≥ %85, model kartı |
| **F4** Kamera | Tapo C200 kurulum, RTSP, yerleşim | Canlı sınıfta 30 dk kararlı çalışma |
| **F5** Cila | Performans, raporlama/dışa aktarım, Docker | Uçtan uca demo |

---

## 5. Süreç kuralları
- **Kimlik:** tüm commit/PR/açıklamalarda yalnızca *Eren KADİROĞLU*. Yardımcı araç dosyaları `.gitignore` ile repo dışında tutulur.
- **CI:** GitHub Actions'a bağımlı değiliz. Tüm kontroller yerelde: `make check` (ruff, mypy, pytest, frontend lint/typecheck/build)
  ve `pre-commit` kancaları. (Public repolarda standart Actions dakikaları ücretsizdir; hesap kilidi yoksa ileride eklenebilir.)
- **Dal stratejisi:** `main` korunur, işler `feat/*`, `fix/*` dallarında; Conventional Commits.
- **Gizli bilgiler:** kamera kullanıcı adı/şifresi yalnızca `.env` içinde, asla repoda değil.
