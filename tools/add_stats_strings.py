"""Adds the performance-card strings to every i18n catalogue and drops the crypto ones.

The catalogues are JSON objects keyed by the English text; tools/translate.py --check requires every language to hold
exactly the keys the code uses. This writes the new keys with a translation per language and removes the keys the
crypto card left behind.

Usage: python tools/add_stats_strings.py
"""
import json
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", "assets", "i18n")

# The keys the code now uses, and their text in each language. English is the key itself.
NEW = {
    "Performance": {
        "en": "Performance", "pt": "Desempenho", "es": "Rendimiento", "de": "Leistung", "fr": "Performances",
        "it": "Prestazioni", "nl": "Prestaties", "pl": "Wydajność", "cs": "Výkon", "da": "Ydeevne",
        "sv": "Prestanda", "nb": "Ytelse", "fi": "Suorituskyky", "ro": "Performanță", "el": "Απόδοση",
        "ru": "Производительность", "uk": "Продуктивність", "tr": "Performans", "hi": "प्रदर्शन",
        "id": "Performa", "vi": "Hiệu suất", "th": "ประสิทธิภาพ", "ja": "パフォーマンス", "ko": "성능",
        "zh-CN": "性能", "zh-TW": "效能",
    },
    "Performance card": {
        "en": "Performance card", "pt": "Cartão de desempenho", "es": "Tarjeta de rendimiento",
        "de": "Leistungskarte", "fr": "Carte de performances", "it": "Scheda prestazioni",
        "nl": "Prestatiekaart", "pl": "Karta wydajności", "cs": "Karta výkonu", "da": "Ydelseskort",
        "sv": "Prestandakort", "nb": "Ytelseskort", "fi": "Suorituskykykortti", "ro": "Card de performanță",
        "el": "Κάρτα απόδοσης", "ru": "Карточка производительности", "uk": "Картка продуктивності",
        "tr": "Performans kartı", "hi": "प्रदर्शन कार्ड", "id": "Kartu performa", "vi": "Thẻ hiệu suất",
        "th": "การ์ดประสิทธิภาพ", "ja": "パフォーマンスカード", "ko": "성능 카드",
        "zh-CN": "性能卡片", "zh-TW": "效能卡片",
    },
    "Frames per second": {
        "en": "Frames per second", "pt": "Quadros por segundo", "es": "Fotogramas por segundo",
        "de": "Bilder pro Sekunde", "fr": "Images par seconde", "it": "Fotogrammi al secondo",
        "nl": "Beelden per seconde", "pl": "Klatki na sekundę", "cs": "Snímky za sekundu",
        "da": "Billeder i sekundet", "sv": "Bilder per sekund", "nb": "Bilder per sekund",
        "fi": "Kuvaa sekunnissa", "ro": "Cadre pe secundă", "el": "Καρέ ανά δευτερόλεπτο",
        "ru": "Кадров в секунду", "uk": "Кадрів за секунду", "tr": "Saniyedeki kare",
        "hi": "फ़्रेम प्रति सेकंड", "id": "Bingkai per detik", "vi": "Khung hình mỗi giây",
        "th": "เฟรมต่อวินาที", "ja": "フレーム/秒", "ko": "초당 프레임",
        "zh-CN": "每秒帧数", "zh-TW": "每秒影格數",
    },
    "CPU": {"en": "CPU"},
    "Memory": {
        "en": "Memory", "pt": "Memória", "es": "Memoria", "de": "Speicher", "fr": "Mémoire", "it": "Memoria",
        "nl": "Geheugen", "pl": "Pamięć", "cs": "Paměť", "da": "Hukommelse", "sv": "Minne", "nb": "Minne",
        "fi": "Muisti", "ro": "Memorie", "el": "Μνήμη", "ru": "Память", "uk": "Пам'ять", "tr": "Bellek",
        "hi": "मेमोरी", "id": "Memori", "vi": "Bộ nhớ", "th": "หน่วยความจำ", "ja": "メモリ", "ko": "메모리",
        "zh-CN": "内存", "zh-TW": "記憶體",
    },
    "Network": {
        "en": "Network", "pt": "Rede", "es": "Red", "de": "Netzwerk", "fr": "Réseau", "it": "Rete",
        "nl": "Netwerk", "pl": "Sieć", "cs": "Síť", "da": "Netværk", "sv": "Nätverk", "nb": "Nettverk",
        "fi": "Verkko", "ro": "Rețea", "el": "Δίκτυο", "ru": "Сеть", "uk": "Мережа", "tr": "Ağ",
        "hi": "नेटवर्क", "id": "Jaringan", "vi": "Mạng", "th": "เครือข่าย", "ja": "ネットワーク",
        "ko": "네트워크", "zh-CN": "网络", "zh-TW": "網路",
    },
    "No network": {
        "en": "No network", "pt": "Sem rede", "es": "Sin red", "de": "Kein Netzwerk", "fr": "Aucun réseau",
        "it": "Nessuna rete", "nl": "Geen netwerk", "pl": "Brak sieci", "cs": "Žádná síť",
        "da": "Intet netværk", "sv": "Inget nätverk", "nb": "Ingen nettverk", "fi": "Ei verkkoa",
        "ro": "Fără rețea", "el": "Χωρίς δίκτυο", "ru": "Нет сети", "uk": "Немає мережі",
        "tr": "Ağ yok", "hi": "कोई नेटवर्क नहीं", "id": "Tidak ada jaringan", "vi": "Không có mạng",
        "th": "ไม่มีเครือข่าย", "ja": "ネットワークなし", "ko": "네트워크 없음",
        "zh-CN": "无网络", "zh-TW": "無網路",
    },
    "Network: {link}": {
        "en": "Network: {link}", "pt": "Rede: {link}", "es": "Red: {link}", "de": "Netzwerk: {link}",
        "fr": "Réseau : {link}", "it": "Rete: {link}", "nl": "Netwerk: {link}", "pl": "Sieć: {link}",
        "cs": "Síť: {link}", "da": "Netværk: {link}", "sv": "Nätverk: {link}", "nb": "Nettverk: {link}",
        "fi": "Verkko: {link}", "ro": "Rețea: {link}", "el": "Δίκτυο: {link}", "ru": "Сеть: {link}",
        "uk": "Мережа: {link}", "tr": "Ağ: {link}", "hi": "नेटवर्क: {link}", "id": "Jaringan: {link}",
        "vi": "Mạng: {link}", "th": "เครือข่าย: {link}", "ja": "ネットワーク: {link}",
        "ko": "네트워크: {link}", "zh-CN": "网络：{link}", "zh-TW": "網路：{link}",
    },
    "Network: {name}  ·  {ip}": {
        "en": "Network: {name}  ·  {ip}", "pt": "Rede: {name}  ·  {ip}", "es": "Red: {name}  ·  {ip}",
        "de": "Netzwerk: {name}  ·  {ip}", "fr": "Réseau : {name}  ·  {ip}", "it": "Rete: {name}  ·  {ip}",
        "nl": "Netwerk: {name}  ·  {ip}", "pl": "Sieć: {name}  ·  {ip}", "cs": "Síť: {name}  ·  {ip}",
        "da": "Netværk: {name}  ·  {ip}", "sv": "Nätverk: {name}  ·  {ip}", "nb": "Nettverk: {name}  ·  {ip}",
        "fi": "Verkko: {name}  ·  {ip}", "ro": "Rețea: {name}  ·  {ip}", "el": "Δίκτυο: {name}  ·  {ip}",
        "ru": "Сеть: {name}  ·  {ip}", "uk": "Мережа: {name}  ·  {ip}", "tr": "Ağ: {name}  ·  {ip}",
        "hi": "नेटवर्क: {name}  ·  {ip}", "id": "Jaringan: {name}  ·  {ip}", "vi": "Mạng: {name}  ·  {ip}",
        "th": "เครือข่าย: {name}  ·  {ip}", "ja": "ネットワーク: {name}  ·  {ip}",
        "ko": "네트워크: {name}  ·  {ip}", "zh-CN": "网络：{name}  ·  {ip}", "zh-TW": "網路：{name}  ·  {ip}",
    },
    "Address {ip}": {
        "en": "Address {ip}", "pt": "Endereço {ip}", "es": "Dirección {ip}", "de": "Adresse {ip}",
        "fr": "Adresse {ip}", "it": "Indirizzo {ip}", "nl": "Adres {ip}", "pl": "Adres {ip}",
        "cs": "Adresa {ip}", "da": "Adresse {ip}", "sv": "Adress {ip}", "nb": "Adresse {ip}",
        "fi": "Osoite {ip}", "ro": "Adresă {ip}", "el": "Διεύθυνση {ip}", "ru": "Адрес {ip}",
        "uk": "Адреса {ip}", "tr": "Adres {ip}", "hi": "पता {ip}", "id": "Alamat {ip}", "vi": "Địa chỉ {ip}",
        "th": "ที่อยู่ {ip}", "ja": "アドレス {ip}", "ko": "주소 {ip}", "zh-CN": "地址 {ip}", "zh-TW": "位址 {ip}",
    },
    "format|EEE d MMM": {
        "en": "EEE d MMM", "pt": "EEE, d MMM", "es": "EEE d MMM", "de": "EEE, d. MMM", "fr": "EEE d MMM",
        "it": "EEE d MMM", "nl": "EEE d MMM", "pl": "EEE, d MMM", "cs": "EEE d. MMM", "da": "EEE d. MMM",
        "sv": "EEE d MMM", "nb": "EEE d. MMM", "fi": "EEE d. MMM", "ro": "EEE, d MMM", "el": "EEE d MMM",
        "ru": "EEE, d MMM", "uk": "EEE, d MMM", "tr": "d MMM EEE", "hi": "EEE d MMM", "id": "EEE, d MMM",
        "vi": "EEE, d MMM", "th": "EEE d MMM", "ja": "M月d日(E)", "ko": "M월 d일 (E)", "zh-CN": "M月d日 EEE",
        "zh-TW": "M月d日 EEE",
    },
}

# Keys the crypto card used; nothing reads them any more.
OBSOLETE = [
    "Turn on the Quotes widget to pick its coins.",
    "prices from {ago}",
]


def main():
    changed = 0
    for name in sorted(os.listdir(ROOT)):
        if not name.endswith(".json"):
            continue
        lang = name[:-5]
        path = os.path.join(ROOT, name)
        with open(path, encoding="utf-8") as f:
            cat = json.load(f)
        for key, texts in NEW.items():
            value = texts.get(lang)
            if value is None:
                # A language the table doesn't name falls back to the English text, which is what the app shows anyway.
                value = key
            cat[key] = value
        for key in OBSOLETE:
            cat.pop(key, None)
        # Sorted like the other catalogues: the file stays readable in a diff.
        ordered = {k: cat[k] for k in sorted(cat)}
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(ordered, f, ensure_ascii=False, indent=2)
            f.write("\n")
        changed += 1
    print("updated", changed, "catalogues")


if __name__ == "__main__":
    main()
