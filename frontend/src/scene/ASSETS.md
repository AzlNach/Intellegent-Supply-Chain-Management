# ASSETS.md — Panduan & Katalog Sprite Pixel Art Isometric

Dokumen ini memuat panduan gaya visual dan spesifikasi teknis untuk setiap aset sprite di dalam virtual office Divisi SCDS-OR.

---

## 1. Panduan Gaya Visual (Style Guide)

- **Proyeksi**: Isometric klasik dengan rasio aspek **2:1** (2 piksel horizontal banding 1 piksel vertikal).
- **Ukuran Ubin Standar (Tile)**: 32 piksel lebar x 16 piksel tinggi.
- **Arah Pencahayaan**: Cahaya utama datang dari arah **kiri atas** (top-left). Sisi menghadap atas dan kiri mendapat warna *highlight*, sisi menghadap kanan dan bawah mendapat bayangan (*shadow*).
- **Garis Tepi (Outline)**: Tepi gelap 1 piksel (*1-pixel dark outline*), menggunakan warna turunan gelap dari objek (bukan murni hitam pekat #000000 agar menyatu harmonis).
- **Palet Warna Terbatas (Warm Retro Office)**:
  - Dinding: `#2b2d5c` (Night purple-blue), `#1e2044` (Shadow), `#3b3d75` (Highlight)
  - Lantai checkerboard: `#e8c18a` (Krem hangat), `#c9945a` (Cokelat tan muda)
  - Kayu meja & rak: `#b5651d` (Base wood), `#8c4b11` (Shadow), `#d9822b` (Highlight)
  - Layar CRT: `#5cff7a` (Hijau fosfor retro aktif), `#1a472a` (Layar padam)
  - Cahaya lampu meja & matahari: `#ffd27a` (Warm amber glow), `#ffe5a3` (Core)
  - Tanaman: `#2e7d32` (Daun), `#1b5e20` (Shadow), `#b45309` (Pot terakota)

---

## 2. Struktur Atlas & Loader

Aplikasi dirancang untuk:
1. Memuat file `assets/atlas.json` dan `assets/atlas.png` jika tersedia.
2. Jika kedua file tersebut tidak ditemukan, engine secara otomatis menghasilkan **sprite prosedural pixel art** langsung di memori dengan ukuran, rasio, bayangan, dan anchor yang identik. Aplikasi dapat berjalan 100% tanpa file gambar eksternal.

---

## 3. Katalog Sprite

| Nama Sprite | Ukuran (Px) | Anchor (X, Y) | Jumlah Frame | Deskripsi |
|---|---|---|---|---|
| `floor_tile_light` | 32 x 16 | (0.5, 0.0) | 1 | Ubin isometric warna krem hangat `#e8c18a` |
| `floor_tile_dark` | 32 x 16 | (0.5, 0.0) | 1 | Ubin isometric warna cokelat tan `#c9945a` |
| `wall_segment_nw` | 32 x 72 | (0.5, 1.0) | 1 | Segmen dinding kiri (North-West) warna `#2b2d5c` dengan lis bawah |
| `wall_segment_ne` | 32 x 72 | (0.5, 1.0) | 1 | Segmen dinding kanan (North-East) warna `#2b2d5c` dengan lis bawah |
| `window_nw` | 40 x 56 | (0.5, 1.0) | 2 | Jendela dengan kisi kayu & cahaya tembus matahari |
| `bookcase` | 32 x 54 | (0.5, 0.85) | 1 | Rak buku kayu jati dengan deretan buku warna-warni |
| `plant_potted` | 24 x 36 | (0.5, 0.85) | 1 | Pot terakota dengan daun tanaman hias rimbun |
| `desk_workstation` | 64 x 48 | (0.5, 0.75) | 1 | Meja kerja kayu berisi monitor CRT layar hijau dan lampu meja kuning |
| `chair_se` | 24 x 32 | (0.5, 0.75) | 1 | Kursi kantor ergonomis menghadap South-East |
| `chair_sw` | 24 x 32 | (0.5, 0.75) | 1 | Kursi kantor ergonomis menghadap South-West |
| `chair_ne` | 24 x 32 | (0.5, 0.75) | 1 | Kursi kantor ergonomis menghadap North-East |
| `chair_nw` | 24 x 32 | (0.5, 0.75) | 1 | Kursi kantor ergonomis menghadap North-West |
| `monitor_crt` | 22 x 22 | (0.5, 0.8) | 2 | Monitor tabung CRT beige retro dengan layar hijau bercahaya |
| `desk_lamp` | 14 x 24 | (0.5, 0.9) | 1 | Lampu leher angsa kuningan dengan tudung kuning bercahaya |
| `whiteboard` | 80 x 48 | (0.5, 1.0) | 1 | Papan tulis dinding aluminium dengan tabel parameter 5 baris |
| `solver_rack` | 44 x 62 | (0.5, 0.85) | 4 | Server rack mainframe dengan baris LED indikator status |
| `head_desk` | 72 x 52 | (0.5, 0.75) | 1 | Meja eksekutif kayu kenari dengan plakat "HEAD SCDS-OR (KOSONG)" |
| `char_ie_idle` | 24 x 36 | (0.5, 0.85) | 4 | IE Agent duduk mengetik santai di meja kerja |
| `char_ie_working` | 24 x 36 | (0.5, 0.85) | 4 | IE Agent mengetik cepat aktif |
| `char_ie_walk` | 24 x 36 | (0.5, 0.85) | 8 | Siklus jalan 4 arah (North-West, North-East, South-West, South-East) |
| `char_ie_read` | 24 x 36 | (0.5, 0.85) | 2 | IE Agent berdiri menghadap papan tulis |
