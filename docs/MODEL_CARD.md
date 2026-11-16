# Model kartı — VibeSight ifade sınıflandırıcısı

> Bu kart eğitim tamamlandığında `training/train.py` çıktısındaki `metrics.json` değerleriyle güncellenir.

| Alan | Değer |
|---|---|
| Görev | Tek yüz görüntüsünden 8 sınıflı yüz ifadesi olasılıkları |
| Sınıflar | nötr, mutlu, şaşkın, üzgün, kızgın, hoşnutsuz (iğrenme), endişeli (korku), küçümseyen |
| Mimari | ConvNeXt-Tiny (ImageNet-22k ön-eğitimli), 112×112 giriş |
| Eğitim verisi | FER2013 görüntüleri + FER+ oy dağılımları (eğitim: ~25k) |
| Kayıp | Soft-label çapraz entropi + label smoothing + sınıf ağırlıkları, MixUp |
| Kalibrasyon | Doğrulama kümesinde sıcaklık ölçekleme (Guo ve ark., 2017) |
| Değerlendirme | FER+ PrivateTest: doğruluk, macro-F1, NLL, ECE, sınıf bazında recall |
| Hedef | Doğruluk ≥ %85, macro-F1 ≥ 0.65 |
| Biçim | ONNX (opset 17), PyTorch ile çıktı farkı < 1e-3 doğrulanır |

## Sonuçlar
*Eğitim sonrası doldurulacak.*

## Bilinen sınırlamalar
- FER2013 düşük çözünürlüklü, ağırlıklı olarak web'den toplanmış, poz verilmiş ifadeler içerir;
  doğal sınıf ortamındaki ince ifadelerde başarım düşer.
- "Hoşnutsuz" ve "küçümseyen" sınıfları çok az örneğe sahiptir; bu sınıfların recall değeri düşüktür.
- Yaş, ten rengi ve cinsiyet gruplarına göre başarım ölçülmemiştir (veri setinde demografik etiket yoktur).
- Gece görüşü (IR) görüntüleri eğitim dağılımının dışındadır.
- Çıktı bir **ifade** tahminidir; kişinin iç duygusu hakkında kesin bilgi vermez.
