# Etik, gizlilik ve hukuki çerçeve

> Bu belge hukuki danışmanlık değildir. Gerçek bir sınıfta kullanmadan önce kurumunuzun veri sorumlusu veya
> etik kurulu ile görüşün.

## Neden önemli
Yüz görüntüsünden çıkarım yapan sistemler **biyometrik veri** işler. Ayrıca yüz ifadesinden iç duygu çıkarımı
bilimsel olarak tartışmalıdır (Barrett ve ark., 2019). Bu yüzden VibeSight "duygu" ve "psikolojik durum" teşhis etmez;
**gözlenen ifade, enerji ve dikkat göstergelerini** oda düzeyinde gösterir.

## Türkiye — KVKK (6698 sayılı Kanun)
- Yüz verisi **özel nitelikli kişisel veri** (biyometrik) kapsamına girebilir (md. 6).
- Gerekenler: **aydınlatma metni**, katılımcıların **açık rızası**, amaçla sınırlı ve ölçülü işleme.
- 18 yaş altı katılımcılar için **veli rızası** gerekir.

## Avrupa Birliği — Yapay Zekâ Yasası (Regulation (EU) 2024/1689)
- **Madde 5(1)(f):** İşyerlerinde ve **eğitim kurumlarında** duygu tanıma sistemlerinin piyasaya sürülmesi ve kullanılması,
  tıbbi veya güvenlik gerekçeleri dışında **yasaktır** (2 Şubat 2025'ten itibaren yürürlükte).
- Sonuç: VibeSight AB'deki bir okulda gerçek öğrencilerin değerlendirilmesi için **kullanılamaz**.

## VibeSight'ın tasarım gereği aldığı önlemler
| Önlem | Nasıl |
|---|---|
| Görüntü kaydı yok | Kareler yalnızca bellekte işlenir, diske yazılmaz |
| Kimlik tanıma yok | Yüz eşleştirme / kimlik modeli bulunmaz; takip ID'leri geçicidir ve 10 sn sonra silinir |
| Yalnızca toplu veri | SQLite'a yalnızca oda ortalamaları yazılır, kişi düzeyinde hiçbir şey saklanmaz |
| Yerel çalışma | Hiçbir veri buluta gönderilmez |
| Gizlilik modu | Arayüzde "Yüzleri gizle" ile yayın görüntüsünde yüzler pikselleştirilir |
| Saklama süresi | Toplu metrikler varsayılan 30 gün sonra otomatik silinir |
| Dürüst sunum | Arayüz "analiz kapsamı"nı ve ifadelerin kesin duygu olmadığını açıkça yazar |

## Kullanım önerisi
1. Projeyi **akademik demo / araştırma prototipi** olarak konumlandırın.
2. Katılımcılara önceden yazılı bilgi verin ve rızalarını alın; rıza vermeyenler kadraj dışında kalabilmeli.
3. Odaya görünür bir **"Bu alanda anonim görüntü analizi yapılmaktadır"** bildirimi asın.
4. Sonuçları bireyleri değerlendirmek için değil, **ortamı iyileştirmek** (mola zamanı, ders temposu) için kullanın.
