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
| Hedef | Doğruluk ≥ %85 (ulaşılan: %83.4), macro-F1 ≥ 0.65 (ulaşılan: 0.698) |
| Biçim | ONNX (opset 17), PyTorch ile çıktı farkı < 1e-3 doğrulanır |

## Sonuçlar
| Deneme | Ayarlar | Doğrulama (en iyi) | Test doğruluk | Test macro-F1 | ECE |
|---|---|---|---|---|---|
| 1 | ConvNeXt-Tiny, 35 epoch, EMA yok | %84.99 (13. epoch) | %83.64 | 0.704 | 0.025 |
| **2 (kullanılan)** | ConvNeXt-Tiny, 35 epoch, EMA 0.998 | %84.85 (10. epoch, EMA) | **%83.39** | **0.698** | 0.033 |

İki deneme arasındaki fark gürültü düzeyindedir; model FER+ testinde yaklaşık %83.5'te dengelenir.
Sıcaklık ölçekleme (T = 0.62) kalibrasyon hatasını 0.114'ten 0.033'e indirmiştir.

### Sınıf bazında recall (deneme 2, test)
| Nötr | Mutlu | Şaşkın | Üzgün | Kızgın | Hoşnutsuz | Endişeli | Küçümseyen |
|---|---|---|---|---|---|---|---|
| 0.815 | 0.917 | 0.863 | 0.754 | 0.809 | 0.773 | 0.707 | 0.462 |

En sık karışmalar: üzgün ↔ nötr (0.12 / 0.11), korku → şaşkın (0.17), küçümseme → nötr ve iğrenme (0.15).

### Olası iyileştirmeler
- 160×160 giriş çözünürlüğü, RAF-DB ile ek eğitim (gerçek dünya görüntüleri)
- Birkaç modelin topluluk (ensemble) ortalaması

## Bilinen sınırlamalar
- FER2013 düşük çözünürlüklü, ağırlıklı olarak web'den toplanmış, poz verilmiş ifadeler içerir;
  doğal sınıf ortamındaki ince ifadelerde başarım düşer.
- "Hoşnutsuz" ve "küçümseyen" sınıfları çok az örneğe sahiptir; bu sınıfların recall değeri düşüktür.
- Yaş, ten rengi ve cinsiyet gruplarına göre başarım ölçülmemiştir (veri setinde demografik etiket yoktur).
- Gece görüşü (IR) görüntüleri eğitim dağılımının dışındadır.
- Çıktı bir **ifade** tahminidir; kişinin iç duygusu hakkında kesin bilgi vermez.
