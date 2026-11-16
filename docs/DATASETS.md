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
| emotion-ferplus-8 (ONNX Model Zoo) | MIT | Kendi modelimiz eğitilene kadar taban ifade modeli |

Tüm indirmeler `scripts/download_models.py` ile yapılır ve SHA-256 ile doğrulanır.

## Bilinçli olarak kullanılmayanlar
- **Ultralytics YOLOv8/11:** AGPL-3.0 lisansı tüm projeyi AGPL'ye zorlar.
- **InsightFace / SCRFD hazır ağırlıkları:** ticari olmayan kullanım koşulu.
- **Web'den toplanmış, kaynağı belirsiz "emotion dataset" kopyaları:** lisans ve etiket kalitesi doğrulanamıyor.
