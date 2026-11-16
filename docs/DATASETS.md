# Veri setleri ve modeller

Seçim ölçütü: **ücretsiz**, **hakemli yayına dayanan** ve **kaynağı resmî** olan veriler.

## Eğitimde kullanılanlar

| Ad | Kaynak | Lisans / koşul | Kullanım |
|---|---|---|---|
| **FER2013** | Goodfellow ve ark., *Challenges in Representation Learning*, ICML 2013. Kaggle: `deadskull7/fer2013` | Araştırma amaçlı, ücretsiz | 35.887 adet 48×48 gri yüz görüntüsü |
| **FER+** | Barsoum ve ark., *Training Deep Networks for Facial Expression Recognition with Crowd-Sourced Label Distribution*, ICMI 2016. github.com/microsoft/FERPlus | **MIT** | FER2013 için 10 etiketleyicili yeni etiketler (8 sınıf) |

**Neden FER2013'ün orijinal etiketleri değil de FER+?** Orijinal etiketlerdeki insan doğruluğu yaklaşık %65'tir;
FER+ her görüntüyü 10 kişiye yeniden etiketletmiştir. Oy dağılımını doğrudan hedef olarak kullanmak (soft label)
hem doğruluğu hem de olasılıkların güvenilirliğini artırır.

## Opsiyonel (onay gerektirir, ücretsiz)
| Ad | Erişim | Ne katar |
|---|---|---|
| RAF-DB | Akademik e-posta ile talep (whdeng.cn) | Gerçek dünya, renkli, farklı yaş/etnik köken |
| AffectNet | Akademik başvuru (mohammadmahoor.com) | ~290k görüntü + sürekli valans/uyarılmışlık etiketleri |
| DAiSEE | Akademik talep (IIT Hyderabad) | Sınıf ortamına yakın: katılım, sıkılma, kafa karışıklığı |

## Hazır (eğitimsiz) modeller

| Model | Lisans | Rol |
|---|---|---|
| YOLOX-S (Megvii) | Apache-2.0 | Kişi tespiti, COCO mAP 40.5 |
| MediaPipe Face Landmarker (Google) | Apache-2.0 | 478 yüz noktası, göz/çene blendshape'leri, baş pozu |
| **EmotiEffLib `enet_b0_8_va_mtl`** (Savchenko, Sber AI Lab / HSE) | Apache-2.0 (kod ve ağırlık deposu) | **Varsayılan ifade modeli**: 8 ifade + doğrudan valans/uyarılmışlık |
| **EmotiEffLib katılım modeli** (`engagement_single_attention.h5`) | Apache-2.0 | **Öğrenilmiş katılım**: ifade ağının 1280 boyutlu yüz özniteliklerinden oluşan diziden katılımcı/dalgın olasılığı (EngageWild) |

### Neden varsayılan ifade modeli EmotiEffLib?
Kendi FER+ modelimiz FER+ testinde %83.4 doğruluk verdi, ama canlı webcam testinde ifadeleri zayıf yakaladı.
Nedeni veri: FER2013, 48×48 piksellik **gri** ve çoğunlukla **poz verilmiş** web fotoğraflarıdır. Webcam yüzünü
48 piksele indirmek renk ve ince ayrıntıyı (göz kırışığı, dudak köşesi) siler.

EmotiEffLib modelleri **AffectNet** (~290 bin gerçek dünya fotoğrafı) ile **224×224 renkli** girdide eğitilmiştir:
- AffectNet 8 sınıf doğruluğu: **%61.9** (AffectNet'te insanlar arası uyum da ~%60 civarıdır; bu veri setinde en iyi
  tek modeller %62–65 aralığındadır, yani bu sayı FER+'daki %83 ile doğrudan kıyaslanamaz).
- Aynı ağ hem ifadeyi hem de **valans ve uyarılmışlığı** doğrudan tahmin eder; çember eşlemesine gerek kalmaz.
- EmotiW / ABAW yarışmalarında üst sıralar; çevrimiçi derslerde **katılım tespiti** için yayımlanmıştır
  (Savchenko ve ark., *IEEE Transactions on Affective Computing*, 2022).
- CPU'da yüz başına ~15 ms, 16 MB.

Not: Model ağırlıkları AffectNet ile eğitildi; AffectNet'in kullanım koşulları araştırma amaçlıdır. Projenin akademik
demo konumlandırması (bkz. `ETHICS_KVKK.md`) bununla uyumludur; ticari kullanım öncesi ayrıca değerlendirilmelidir.

Kendi modelimize geçmek için: `backend\.env` içine `VIBESIGHT_EMOTION_MODEL=emotion.onnx`.

### Doğrulama
- **İfade hattı:** EmotiEffLib'in kendi test fotoğrafında resmî beklenti `[Mutlu, Kızgın, Mutlu]`. Hattımız
  (YOLOX + MediaPipe + MTCNN eşdeğeri kırpma) aynı sonucu verir; `backend/tests/test_models.py` bunu her
  çalıştırmada denetler. Kırpma çerçevesi MTCNN kutusuna göre ölçülerek ayarlandı (yüz yüksekliğinin %11'i yukarı).
- **Katılım modeli:** Orijinal Keras modeli TensorFlow ile çalıştırılıp bizim NumPy uyarlamamızla karşılaştırıldı;
  gerçek yüz özniteliklerinde en büyük fark 8.6×10⁻⁸ (birebir aynı model).
- **Bilinen sınır:** Katılım modeli çevrimiçi derste dizüstü kamerasına bakan öğrencilerle eğitildi; sınıfın
  uzağından çeken bir kamerada başarımı ayrıca doğrulanmalıdır. Hareketsiz görüntüde (fotoğraf) "dalgın" der.

Tüm indirmeler `scripts/download_models.py` ile yapılır ve SHA-256 ile doğrulanır.

## Bilinçli olarak kullanılmayanlar
- **Ultralytics YOLOv8/11:** AGPL-3.0 lisansı tüm projeyi AGPL'ye zorlar.
- **InsightFace / SCRFD hazır ağırlıkları:** ticari olmayan kullanım koşulu.
- **LibreFace (USC):** güçlü, ama "USC Research License" ile kısıtlı lisanslı.
- **OpenFace 2.0:** akademik, ticari olmayan lisans; ayrıca ağır C++ bağımlılıkları.
- **Web'den toplanmış, kaynağı belirsiz "emotion dataset" kopyaları:** lisans ve etiket kalitesi doğrulanamıyor.
