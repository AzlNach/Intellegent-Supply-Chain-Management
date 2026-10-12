# Handoff Backend — Stock Memory Copilot

Versi API: v0.2  
Tanggal: 10 Oktober 2026  
Penanggung jawab: Anggota B

## 1. Akses

```text
Backend:


Swagger:
https://stock-copilot-backend.onrender.com/docs

OpenAPI:
https://stock-copilot-backend.onrender.com/openapi.json

Repository:
https://github.com/dhivics9/stock-copilot-backend

Firebase project: stock-helper-46483
Firestore: (default)
Store demo: demo-store
```

Endpoint bisnis memakai header berikut. Nilai token dibagikan privat.

```http
X-Dev-Token: <token>
Content-Type: application/json
```

## 2. Struktur database

```text
stores/{store_id}
├── products/{product_id}
│   └── events/{event_id}
├── tasks/{task_id}
│   └── events/{event_id}
└── proposed_updates/{update_id}
```

### Produk

| Bagian | Field |
|---|---|
| Identitas | `product_id`, `name`, `unit` |
| Metadata | `revision`, `updated_at` |
| `facts` | `on_hand_qty`, `stock_as_of`, `stock_source`, `incoming_orders`, `incoming_checked_at`, `incoming_source` |
| `policy` | `target_qty`, `source` |

Setiap objek dalam `incoming_orders`:

```text
order_id
status: ordered / in_transit / received / cancelled
remaining_qty
expected_arrival_at
eta_verified_at
```

### Task

```text
task_id, store_id, product_id
operation: target_gap

parameters:
  required_by
  target_qty
  expected_outgoing_qty

revision, status, pending_update_ids
validation, result
created_at, updated_at
```

### Usulan perubahan

```text
update_id, product_id, task_id (opsional)
base_product_revision
old_values, new_values, source_ref
request_payload
status: PENDING / APPROVED / REJECTED
created_at + metadata approval/rejection
```

Relasi utama: satu produk dapat memiliki banyak task/proposal. `facts`, `policy`, `validation`, dan `result` adalah objek dalam dokumen, bukan koleksi terpisah.

## 3. Endpoint

| Kelompok | Method dan endpoint |
|---|---|
| Health | `GET /health` |
| Database health | `GET /health/database` |
| Daftar produk | `GET /products` |
| Tambah produk | `POST /products` |
| State produk | `GET /products/{product_id}/state` |
| Riwayat produk | `GET /products/{product_id}/events` |
| Buat task | `POST /tasks` |
| State task | `GET /tasks/{task_id}` |
| Isi/koreksi parameter | `PATCH /tasks/{task_id}/parameters` |
| Validasi | `POST /tasks/{task_id}/validate` |
| Riwayat task | `GET /tasks/{task_id}/events` |
| Buat usulan | `POST /updates` |
| Preview usulan | `GET /updates/{update_id}` |
| Setujui usulan | `POST /updates/{update_id}/confirm` |
| Tolak usulan | `POST /updates/{update_id}/reject` |
| Input kalkulator | `GET /tasks/{task_id}/calculation-input` |
| Kalkulator referensi | `POST /tasks/{task_id}/calculate` |
| Simpan hasil kalkulator eksternal | `POST /tasks/{task_id}/result` |

Body dan response lengkap tersedia di Swagger/OpenAPI.

## 4. Kontrak kalkulator

Input angka:

```text
on_hand_qty
eligible_incoming_qty
expected_outgoing_qty
target_qty
```

Rumus:

```text
projected_balance = on_hand_qty + eligible_incoming_qty - expected_outgoing_qty
shortfall = max(0, target_qty - projected_balance)
```

Body untuk menyimpan hasil eksternal:

```json
{
  "product_revision": 2,
  "task_revision": 4,
  "projected_balance": 10,
  "shortfall": 20
}
```

Angka di atas contoh. Gunakan revisi dan input aktual dari `calculation-input`.

Alur:

```text
Buat task → validate → calculation-input
→ kalkulator → kirim result → baca task
```

## 5. Aturan integrasi

- Agent informasi membaca state produk; tidak perlu membuat task kalkulasi.
- Agent perhitungan hanya menghitung setelah `ready: true`.
- `null` berarti belum diketahui; tidak boleh dianggap `0`.
- Timestamp harus mempunyai timezone.
- Semua quantity memakai `unit` produk.
- Default freshness: 12 jam.
- Perubahan fakta melalui proposal → approval.
- Revisi berubah: baca ulang dan validasi ulang.
- Hasil `COMPUTED` adalah hasil historis; keputusan baru memakai task baru.
- Database menjadi sumber fakta; chat lama tidak menimpa fakta yang sudah disetujui.

Status task:

```text
COLLECTING_PARAMETERS
NEEDS_CLARIFICATION
NEEDS_REFRESH
CONFLICT
AWAITING_APPROVAL
READY
COMPUTED
```

Error utama:

| HTTP | Arti |
|---|---|
| `401` | Token tidak valid/tidak dikirim |
| `404` | ID tidak ditemukan |
| `409` | Konflik revisi/status atau task belum siap |
| `422` | Input tidak sesuai schema |

## 6. Pembagian kerja dan status

| Anggota | Bagian |
|---|---|
| A | Frontend/office 3D, panel fakta, status, approval, hasil |
| B | Database, API, schema, validasi kode, audit, hosting |
| C | Dua agent, routing, klarifikasi, konteks sesi, integrasi kalkulator |

Status saat rangkuman dibuat:

- Smoke lokal: `PASS`, 26 pemeriksaan HTTP.
- Render: `Live`.
- Smoke remote: belum dikonfirmasi.
- Session/chat dan integrasi agent: masih perlu dikerjakan.
- Render Free dapat tidur saat tidak digunakan.

Jangan bagikan `.env` atau JSON service account. Anggota pemanggil API cukup mendapatkan URL, kontrak, dan token development secara privat.
