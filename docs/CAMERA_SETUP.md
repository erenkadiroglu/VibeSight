# TP-Link Tapo C200 kurulumu (adım adım)

Bu rehber, kutudan yeni çıkmış bir Tapo C200'ü VibeSight'a bağlamak için gereken her şeyi anlatır.
Toplam süre: yaklaşık 15 dakika.

## Neye ihtiyacınız var
- Tapo C200 ve kutudan çıkan adaptör
- **2.4 GHz** Wi-Fi ağı (C200 5 GHz ağlara bağlanamaz)
- Telefonda **Tapo** uygulaması (App Store / Google Play) ve bir TP-Link hesabı
- VibeSight'ın çalışacağı bilgisayar, kamera ile **aynı ağda** olmalı

## 1. Kamerayı Tapo uygulamasına ekleyin
1. Kamerayı prize takın. Yaklaşık 30 saniye sonra LED **turuncu-yeşil yanıp söner**; bu, eşleşmeye hazır demektir.
   Yanıp sönmüyorsa alttaki **Reset** düğmesine iğneyle 5 saniye basın.
2. Tapo uygulamasında sağ üstteki **+** → **Kameralar** → **C200**.
3. Uygulamanın yönergelerini izleyin: telefon kameranın geçici Wi-Fi'sine (`Tapo_Cam_XXXX`) bağlanır,
   ardından ev/okul Wi-Fi'nizi seçip şifresini girersiniz.
4. Kameraya bir ad verin (ör. `Sinif-1`). Uygulama güncelleme önerirse **firmware'i güncelleyin**.

> **Okul / kurum ağı uyarısı:** Eduroam gibi kullanıcı adı + şifre isteyen (WPA2-Enterprise) ağlar C200 ile çalışmaz.
> Bu durumda bir mobil hotspot veya ayrı bir 2.4 GHz router kullanın; bilgisayar da aynı ağa bağlanmalıdır.

## 2. RTSP için "Kamera Hesabı" oluşturun
VibeSight görüntüyü **RTSP** protokolüyle alır. Bunun için kameraya özel bir kullanıcı adı/şifre gerekir
(bu, TP-Link hesabınızın şifresi **değildir**).

1. Tapo uygulamasında kameraya dokunun → sağ üstteki **⚙ (Ayarlar)**.
2. **Gelişmiş Ayarlar** → **Kamera Hesabı**.
3. Bir kullanıcı adı (ör. `vibesight`) ve **güçlü** bir şifre belirleyin (6–32 karakter). Bunları not edin.

## 3. Kameranın IP adresini bulun ve sabitleyin
1. Tapo uygulamasında: kamera → **⚙** → **Cihaz Bilgisi** → **IP Adresi** (ör. `192.168.1.50`).
2. **Önerilen:** Router arayüzünden bu cihaza **sabit IP (DHCP rezervasyonu)** atayın. Aksi hâlde router yeniden
   başladığında IP değişebilir ve VibeSight bağlanamaz. (Router menüsünde genelde *DHCP → Adres Rezervasyonu* adıyla geçer.)

## 4. Bağlantıyı test edin (VibeSight'dan önce)
RTSP adresleri:

| Akış | Adres | Çözünürlük | Ne zaman |
|---|---|---|---|
| Yüksek | `rtsp://KULLANICI:ŞİFRE@IP:554/stream1` | 1920×1080 | Varsayılan, ifade analizi için gerekli |
| Düşük | `rtsp://KULLANICI:ŞİFRE@IP:554/stream2` | 640×360 | Zayıf Wi-Fi, yalnızca kişi sayımı |

Test için **VLC**: *Medya → Ağ Akışı Aç* → adresi yapıştırın. Görüntü geliyorsa kamera hazır.

Ya da proje içinden:
```bash
make camera-test
```

## 5. VibeSight'ı kameraya bağlayın
`backend/.env` dosyasını oluşturun (yoksa `cp backend/.env.example backend/.env`) ve doldurun:
```dotenv
VIBESIGHT_SOURCE=tapo
VIBESIGHT_TAPO_HOST=192.168.1.50
VIBESIGHT_TAPO_USER=vibesight
VIBESIGHT_TAPO_PASSWORD=sizin-sifreniz
VIBESIGHT_TAPO_STREAM=stream1
```
Sonra `make dev` ile başlatın. Şifre `.env` içinde kalır; bu dosya `.gitignore` sayesinde asla repoya girmez
ve günlüklerde şifre `***` olarak maskelenir.

## 6. Kamerayı doğru yerleştirin (sonuç kalitesini en çok etkileyen adım)
- **Yükseklik:** 2–2.3 m, hafifçe aşağı bakacak şekilde (≈15°). Tavandan dik bakış yüzleri gizler.
- **Konum:** Öğrencilerin baktığı yönde, yani **tahtanın yanında / üstünde**. Arkadan çekim yalnızca sayım verir.
- **Mesafe:** İfade analizi için yüzler görüntüde **en az ~48 piksel** olmalı. 1080p'de bu kabaca **≤ 4–5 m** demektir.
  Arka sıralar sayılır ama ifadeleri ölçülmeyebilir; arayüz bunu "analiz kapsamı" olarak dürüstçe gösterir.
- **Işık:** Pencereyi kameranın **arkasına** alın; ters ışık yüzleri karartır. C200'ün gece görüşü (IR) gri görüntü verir,
  ifade doğruluğu düşer.
- **Ayarlar (Tapo uygulaması):** *Video Kalitesi → 1080p*, *Özel Mod → Kapalı*, gereksizse *Hareket Algılama* bildirimlerini kapatın.
- **Pan/tilt:** C200 döner; yerleştirdikten sonra uygulamadan açıyı ayarlayıp **Ön Ayar Konumu** olarak kaydedin.

## Sorun giderme
| Belirti | Olası neden | Çözüm |
|---|---|---|
| "Kameraya yeniden bağlanılıyor" | Yanlış IP / farklı ağ | IP'yi uygulamadan kontrol edin, bilgisayar aynı Wi-Fi'da mı? |
| VLC'de `401 Unauthorized` | Kamera Hesabı yanlış | 2. adımdaki kullanıcı adı/şifreyi kullanın (TP-Link hesabı değil) |
| Görüntü donuyor / gri bloklar | Zayıf Wi-Fi | Router'ı yaklaştırın veya `VIBESIGHT_TAPO_STREAM=stream2` |
| Gecikme birkaç saniye | Ağ tamponu | VibeSight TCP + düşük tampon kullanır; Wi-Fi sinyalini iyileştirin |
| Bağlantı hiç kurulmuyor | Özel Mod açık | Tapo uygulamasında *Özel Mod*'u kapatın |
| Şifrede `@` veya `:` var | URL'yi bozar | Sorun değil: VibeSight şifreyi otomatik kodlar |
