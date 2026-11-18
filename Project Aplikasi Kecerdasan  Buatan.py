"""StockWise — aplikasi sistem pakar pengadaan bahan baku, versi SATU FILE.

Cara menjalankan (PowerShell / VS Code):
    python app.py

from __future__ import annotations

import json
from copy import deepcopy


# =====================================================================
# 1. BASIS PENGETAHUAN (KNOWLEDGE BASE) — sementara masih satu file
# =====================================================================

THRESHOLDS = {
    "lead_time_long_days": 14,
    "warehouse_nearly_full_pct": 85,
    "demand_increase_pct": 0,
}

EXAMPLE_DATA = {
    "current_stock": 120.0,              # ton
    "reorder_point": 200.0,              # ton
    "daily_demand": 15.0,                # ton per hari
    "demand_change_pct": 15.0,           # persen
    "lead_time_days": 21,                # hari
    "warehouse_utilization_pct": 90,     # persen
    "main_supplier_available": False,
    "backup_supplier_available": True,
}

WHY_QUESTIONS = {
    "Stok saat ini": "Untuk membandingkan jumlah persediaan dengan reorder point dan menghitung berapa hari stok mencukupi.",
    "Reorder point": "Untuk menentukan apakah stok sudah melewati batas yang memicu pemesanan ulang.",
    "Kebutuhan harian": "Untuk menghitung stock coverage = stok dibagi rata-rata kebutuhan harian.",
    "Perubahan permintaan": "Untuk mengetahui apakah kebutuhan bahan baku cenderung meningkat.",
    "Lead time": "Untuk menentukan urgensi pengadaan dan membandingkannya dengan cakupan stok.",
    "Utilisasi gudang": "Untuk menilai apakah pemesanan besar perlu disertai evaluasi kapasitas penyimpanan.",
    "Pemasok utama": "Untuk menentukan tindak lanjut saat pemasok utama tidak dapat memasok bahan.",
    "Pemasok alternatif": "Untuk memeriksa apakah rekomendasi menggunakan pemasok cadangan memungkinkan.",
}

FACT_LABELS = {
    "stock_below_rop": "Stok lebih kecil dari reorder point",
    "demand_increasing": "Permintaan meningkat",
    "long_lead_time": "Lead time panjang",
    "warehouse_nearly_full": "Gudang hampir penuh",
    "coverage_below_lead_time": "Stock coverage lebih pendek dari lead time",
    "main_supplier_unavailable": "Pemasok utama tidak tersedia",
    "backup_supplier_available": "Pemasok alternatif tersedia",
    "reorder_required": "Pemesanan ulang diperlukan",
    "large_order_review": "Perlu evaluasi pesanan lebih besar",
    "urgent_procurement": "Pengadaan mendesak",
    "storage_review": "Perlu evaluasi kapasitas gudang",
    "use_backup_supplier": "Perlu menghubungi pemasok alternatif",
    "manager_approval": "Perlu persetujuan manajer",
    "stockout_risk": "Risiko bahan baku habis sebelum pasokan tiba",
    "supplier_escalation": "Perlu eskalasi masalah pemasok",
    "confirm_main_supplier": "Perlu konfirmasi pemasok utama",
}

# Nilai TRUE/FALSE pada kondisi aturan harus cocok dengan fakta di working memory.
RULES = [
    {
        "id": "R01", "name": "Reorder diperlukan",
        "if": {"stock_below_rop": True},
        "then": {"reorder_required": True},
        "because": "Stok saat ini berada di bawah reorder point.",
    },
    {
        "id": "R02", "name": "Evaluasi jumlah pemesanan",
        "if": {"reorder_required": True, "demand_increasing": True},
        "then": {"large_order_review": True},
        "because": "Pengadaan ulang diperlukan dan permintaan meningkat.",
    },
    {
        "id": "R03", "name": "Pengadaan mendesak",
        "if": {"reorder_required": True, "long_lead_time": True},
        "then": {"urgent_procurement": True},
        "because": "Pengadaan ulang diperlukan dan lead time pemasok panjang.",
    },
    {
        "id": "R04", "name": "Evaluasi kapasitas gudang",
        "if": {"large_order_review": True, "warehouse_nearly_full": True},
        "then": {"storage_review": True},
        "because": "Pemesanan lebih besar sedang dipertimbangkan ketika gudang hampir penuh.",
    },
    {
        "id": "R05", "name": "Gunakan pemasok alternatif",
        "if": {
            "urgent_procurement": True,
            "main_supplier_unavailable": True,
            "backup_supplier_available": True,
        },
        "then": {"use_backup_supplier": True},
        "because": "Pengadaan mendesak, pemasok utama tidak tersedia, dan pemasok alternatif tersedia.",
    },
    {
        "id": "R06", "name": "Persetujuan manajer",
        "if": {"large_order_review": True, "urgent_procurement": True},
        "then": {"manager_approval": True},
        "because": "Pengadaan mendesak dan ada pertimbangan meningkatkan jumlah pesanan.",
    },
    {
        "id": "R07", "name": "Risiko stockout",
        "if": {"coverage_below_lead_time": True},
        "then": {"stockout_risk": True},
        "because": "Perkiraan cakupan stok lebih pendek daripada lead time pemasok.",
    },
    {
        "id": "R08", "name": "Eskalasi pemasok",
        "if": {
            "reorder_required": True,
            "main_supplier_unavailable": True,
            "backup_supplier_available": False,
        },
        "then": {"supplier_escalation": True},
        "because": "Pengadaan diperlukan, tetapi pemasok utama dan cadangan tidak tersedia.",
    },
    {
        "id": "R09", "name": "Mitigasi risiko stockout",
        "if": {"stockout_risk": True},
        "then": {"reorder_required": True, "urgent_procurement": True},
        "because": "Risiko stockout memicu tindakan pengadaan mendesak meskipun stok belum di bawah ROP.",
    },
    {
        "id": "R10", "name": "Konfirmasi pemasok utama",
        "if": {"urgent_procurement": True, "main_supplier_unavailable": False},
        "then": {"confirm_main_supplier": True},
        "because": "Pengadaan mendesak dan pemasok utama masih tersedia.",
    },
]

ACTIONS = {
    "reorder_required": ("Rencanakan pemesanan ulang", "Tinjau kebutuhan material dan mulai proses pengadaan ulang."),
    "large_order_review": ("Evaluasi jumlah pemesanan", "Periksa apakah jumlah pesanan perlu ditambah; sistem tidak menghitung kuantitas optimal."),
    "urgent_procurement": ("Prioritaskan pengadaan", "Koordinasikan peluang percepatan pengiriman bersama purchasing dan pemasok."),
    "storage_review": ("Periksa kapasitas gudang", "Tinjau ruang penyimpanan sebelum menyetujui pesanan lebih besar."),
    "use_backup_supplier": ("Hubungi pemasok alternatif", "Konfirmasi ketersediaan bahan serta perkiraan waktu pengiriman."),
    "manager_approval": ("Minta persetujuan manajer", "Ajukan evaluasi terhadap pembelian mendesak dan kemungkinan pesanan besar."),
    "stockout_risk": ("Antisipasi kekurangan bahan", "Tinjau langkah untuk mencegah produksi berhenti sebelum pasokan tiba."),
    "supplier_escalation": ("Eskalasi kendala pemasok", "Laporkan bahwa pemasok utama dan cadangan tidak tersedia; evaluasi sumber lain."),
    "confirm_main_supplier": ("Konfirmasi jadwal pemasok utama", "Pastikan pemasok utama sanggup mengirim dalam waktu yang dibutuhkan."),
}


# =====================================================================
# 2. PEMBENTUKAN FAKTA — dari input angka menjadi TRUE / FALSE
# =====================================================================

def build_facts(data: dict) -> tuple[dict, dict]:
    """Menghasilkan fakta awal dan metrik terhitung."""
    if data["daily_demand"] <= 0:
        raise ValueError("Kebutuhan harian harus lebih besar daripada 0.")
    if any(data[key] < 0 for key in ("current_stock", "reorder_point", "lead_time_days")):
        raise ValueError("Stok, reorder point, dan lead time tidak boleh negatif.")
    if not 0 <= data["warehouse_utilization_pct"] <= 100:
        raise ValueError("Utilisasi gudang harus berada pada rentang 0–100%.")

    coverage = data["current_stock"] / data["daily_demand"]
    lead = data["lead_time_days"]
    facts = {
        "stock_below_rop": data["current_stock"] < data["reorder_point"],
        "demand_increasing": data["demand_change_pct"] > THRESHOLDS["demand_increase_pct"],
        "long_lead_time": lead > THRESHOLDS["lead_time_long_days"],
        "warehouse_nearly_full": data["warehouse_utilization_pct"] > THRESHOLDS["warehouse_nearly_full_pct"],
        "coverage_below_lead_time": coverage < lead,
        "main_supplier_unavailable": not data["main_supplier_available"],
        "backup_supplier_available": data["backup_supplier_available"],
    }
    metrics = {
        "coverage_days": round(coverage, 2),
        "lead_time_days": lead,
        "gap_days": round(max(0, lead - coverage), 2),
    }
    return facts, metrics


# =====================================================================
# 3. FORWARD CHAINING — 1 aturan per langkah + conflict set
# =====================================================================

def matches(rule: dict, memory: dict) -> bool:
    # Fakta yang tidak ada bukan berarti False.
    return all(key in memory and memory[key] == required
               for key, required in rule["if"].items())


def forward_chaining(initial_facts: dict) -> dict:
    memory = dict(initial_facts)  # working memory
    fired = set()                 # aturan yang sudah dijalankan
    trace = []

    while True:
        eligible = [rule for rule in RULES if rule["id"] not in fired and matches(rule, memory)]
        conflict_set = [rule["id"] for rule in eligible]
        if not eligible:
            break

        # Conflict resolution: pilih aturan dengan urutan ID terkecil.
        rule = eligible[0]
        before = dict(memory)
        additions = {}

        for key, value in rule["then"].items():
            if key in memory and memory[key] != value:
                raise ValueError(f"Konflik aturan {rule['id']} pada fakta {key}.")
            if key not in memory:
                memory[key] = value
                additions[key] = value

        fired.add(rule["id"])
        trace.append({
            "step": len(trace) + 1,
            "rule_id": rule["id"],
            "rule_name": rule["name"],
            "conflict_set": conflict_set,
            "conditions": dict(rule["if"]),
            "added_facts": additions,
            "memory_before": before,
            "memory_after": dict(memory),
            "reason": rule["because"],
        })

    return {"memory": memory, "trace": trace, "fired_rules": [x["rule_id"] for x in trace]}


def analyze(data: dict) -> dict:
    initial, metrics = build_facts(data)
    inference = forward_chaining(initial)
    memory = inference["memory"]

    if memory.get("stockout_risk", False):
        status = "KRITIS"
    elif memory.get("urgent_procurement", False):
        status = "MENDESAK"
    elif memory.get("reorder_required", False):
        status = "PERLU PENGADAAN"
    else:
        status = "TERKENDALI"

    recommendations = [
        {"key": key, "title": title, "detail": detail}
        for key, (title, detail) in ACTIONS.items()
        if memory.get(key, False)
    ]

    return {
        "input": deepcopy(data), "initial_facts": initial,
        "metrics": metrics, "status": status,
        "recommendations": recommendations,
        **inference,
    }


# =====================================================================
# 4. INTERFACE WEBSITE STREAMLIT
# =====================================================================

def status_box(st, status: str) -> None:
    message = {
        "KRITIS": "🔴 KRITIS — Stok berisiko habis sebelum pasokan datang.",
        "MENDESAK": "🟠 MENDESAK — Pengadaan perlu segera diprioritaskan.",
        "PERLU PENGADAAN": "🟡 PERLU PENGADAAN — Rencanakan pemesanan ulang.",
        "TERKENDALI": "🟢 TERKENDALI — Belum ada tindakan pengadaan yang dipicu aturan.",
    }[status]
    if status == "KRITIS":
        st.error(message)
    elif status in ("MENDESAK", "PERLU PENGADAAN"):
        st.warning(message)
    else:
        st.success(message)


def input_form(st, prefix: str, defaults: dict) -> dict | None:
    """Form sama untuk analisis normal dan simulasi what-if."""
    with st.form(f"{prefix}_form"):
        st.subheader("Data persediaan bahan baku PP")
        left, right = st.columns(2)
        with left:
            stock = st.number_input("Stok saat ini (ton)", min_value=0.0, value=float(defaults["current_stock"]), step=5.0, key=f"{prefix}_stock", help=WHY_QUESTIONS["Stok saat ini"])
            rop = st.number_input("Reorder point (ton)", min_value=0.0, value=float(defaults["reorder_point"]), step=5.0, key=f"{prefix}_rop", help=WHY_QUESTIONS["Reorder point"])
            daily = st.number_input("Kebutuhan harian (ton/hari)", min_value=0.1, value=float(defaults["daily_demand"]), step=0.5, key=f"{prefix}_daily", help=WHY_QUESTIONS["Kebutuhan harian"])
            trend = st.number_input("Perubahan permintaan (%)", min_value=-100.0, max_value=500.0, value=float(defaults["demand_change_pct"]), step=5.0, key=f"{prefix}_trend", help=WHY_QUESTIONS["Perubahan permintaan"])
        with right:
            lead = st.number_input("Lead time pemasok (hari)", min_value=0, value=int(defaults["lead_time_days"]), step=1, key=f"{prefix}_lead", help=WHY_QUESTIONS["Lead time"])
            warehouse = st.slider("Utilisasi gudang (%)", min_value=0, max_value=100, value=int(defaults["warehouse_utilization_pct"]), key=f"{prefix}_warehouse", help=WHY_QUESTIONS["Utilisasi gudang"])
            supplier_opts = ["Tersedia", "Tidak tersedia"]
            main = st.selectbox("Pemasok utama", supplier_opts, index=0 if defaults["main_supplier_available"] else 1, key=f"{prefix}_main", help=WHY_QUESTIONS["Pemasok utama"])
            backup = st.selectbox("Pemasok alternatif", supplier_opts, index=0 if defaults["backup_supplier_available"] else 1, key=f"{prefix}_backup", help=WHY_QUESTIONS["Pemasok alternatif"])
        submitted = st.form_submit_button("🔎 Jalankan analisis", type="primary", use_container_width=True)
    if not submitted:
        return None
    return {
        "current_stock": stock,
        "reorder_point": rop,
        "daily_demand": daily,
        "demand_change_pct": trend,
        "lead_time_days": lead,
        "warehouse_utilization_pct": warehouse,
        "main_supplier_available": main == "Tersedia",
        "backup_supplier_available": backup == "Tersedia",
    }


def show_metrics(st, result: dict) -> None:
    data, metrics = result["input"], result["metrics"]
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Stok", f"{data['current_stock']:,.1f} ton")
    col2.metric("Reorder point", f"{data['reorder_point']:,.1f} ton")
    col3.metric("Stock coverage", f"{metrics['coverage_days']:,.1f} hari")
    col4.metric("Lead time", f"{metrics['lead_time_days']} hari")
    if metrics["gap_days"] > 0:
        st.caption(f"Selisih cakupan stok terhadap lead time = {metrics['gap_days']:.1f} hari. Ini indikator potensi kekurangan stok, bukan perkiraan pasti.")


def show_recommendations(st, result: dict) -> None:
    st.subheader("Rekomendasi tindakan")
    if not result["recommendations"]:
        st.info("Belum ada rekomendasi pengadaan yang dipicu oleh aturan saat ini.")
    for n, item in enumerate(result["recommendations"], 1):
        with st.expander(f"{n}. {item['title']}", expanded=(n <= 2)):
            st.write(item["detail"])
            st.caption(f"Fakta hasil inferensi: {item['key']}")


def show_result(st, result: dict, *, download: bool = True) -> None:
    status_box(st, result["status"])
    show_metrics(st, result)
    st.caption(f"Aturan dijalankan: {', '.join(result['fired_rules']) or 'tidak ada'}")
    show_recommendations(st, result)
    if download:
        st.download_button(
            "⬇️ Download hasil analisis (JSON)",
            data=json.dumps(result, ensure_ascii=False, indent=2),
            file_name="stockwise_hasil.json",
            mime="application/json",
        )


def dashboard_page(st) -> None:
    st.title("📦 StockWise")
    st.subheader("Sistem Pakar Pengadaan Bahan Baku")
    st.write("Aplikasi ini membantu mengevaluasi persediaan biji plastik PP menggunakan metode **forward chaining**.")
    a, b, c = st.columns(3)
    a.info("**1. Input**\n\nMasukkan stok, permintaan, gudang, dan kondisi pemasok.")
    b.info("**2. Inferensi**\n\nSistem mencocokkan fakta dengan 10 aturan IF–THEN.")
    c.info("**3. Rekomendasi**\n\nLihat tindakan yang disarankan dan alasan aturannya.")
    st.divider()
    if "result" in st.session_state:
        st.subheader("Hasil analisis terakhir")
        status_box(st, st.session_state["result"]["status"])
        show_metrics(st, st.session_state["result"])
    else:
        st.info("Mulai dari menu **Analisis Persediaan** di sebelah kiri.")
    st.warning("Ini prototipe tugas besar. Ambang batas dan aturan masih contoh dan perlu divalidasi dengan sumber pengetahuan yang relevan.")


def analysis_page(st) -> None:
    st.title("🧮 Analisis Persediaan")
    values = input_form(st, "main", st.session_state.get("last_input", EXAMPLE_DATA))
    if values is not None:
        try:
            st.session_state["result"] = analyze(values)
            st.session_state["last_input"] = values
            st.session_state.pop("simulation_result", None)
        except ValueError as exc:
            st.error(f"Data tidak valid: {exc}")
    if "result" in st.session_state:
        st.divider()
        show_result(st, st.session_state["result"])


def explanation_page(st) -> None:
    st.title("🧠 Penjelasan Forward Chaining")
    if "result" not in st.session_state:
        st.info("Jalankan Analisis Persediaan terlebih dahulu.")
        return
    result = st.session_state["result"]
    tab1, tab2, tab3 = st.tabs(["HOW: Jejak inferensi", "WHY: Alasan pertanyaan", "Working memory"])
    with tab1:
        st.write("Setiap iterasi dipilih satu aturan yang aktif dan belum dijalankan. Jika beberapa aturan aktif bersamaan, urutan nomor aturan menjadi prioritas.")
        if not result["trace"]:
            st.info("Tidak ada aturan yang aktif pada kondisi ini.")
        for event in result["trace"]:
            with st.expander(f"Langkah {event['step']}: {event['rule_id']} — {event['rule_name']}", expanded=False):
                st.write("**Conflict set:**", ", ".join(event["conflict_set"]))
                st.write("**Alasan:**", event["reason"])
                st.write("**Kondisi aturan:**", event["conditions"])
                st.write("**Fakta baru:**", event["added_facts"] or "Tidak ada fakta baru; kesimpulan sudah diketahui")
                st.write("**Working memory sebelum aturan:**")
                st.json(event["memory_before"])
                st.write("**Working memory setelah aturan:**")
                st.json(event["memory_after"])
        st.success("Proses berhenti karena tidak ada aturan lain yang aktif dan belum dijalankan.")
    with tab2:
        st.write("Setiap input memiliki tujuan di dalam logika keputusan:")
        for question, why in WHY_QUESTIONS.items():
            st.markdown(f"**Mengapa menanyakan {question.lower()}?**  \n{why}")
    with tab3:
        st.subheader("Fakta awal")
        st.table([{"Fakta": FACT_LABELS.get(k, k), "Nilai": "TRUE" if v else "FALSE"} for k, v in result["initial_facts"].items()])
        st.subheader("Working memory akhir")
        st.table([{"Fakta": FACT_LABELS.get(k, k), "Nilai": "TRUE" if v else "FALSE"} for k, v in result["memory"].items()])


def simulation_page(st) -> None:
    st.title("🔁 Simulasi What-if")
    if "result" not in st.session_state:
        st.info("Jalankan Analisis Persediaan terlebih dahulu sebagai skenario awal.")
        return
    original = st.session_state["result"]
    st.write("Ubah satu atau beberapa kondisi, kemudian bandingkan dengan hasil sebelumnya.")
    data = input_form(st, "simulation", original["input"])
    if data is not None:
        try:
            st.session_state["simulation_result"] = analyze(data)
        except ValueError as exc:
            st.error(str(exc))
    if "simulation_result" in st.session_state:
        changed = st.session_state["simulation_result"]
        left, right = st.columns(2)
        with left:
            st.subheader("Sebelum")
            status_box(st, original["status"])
            st.write("Aturan:", ", ".join(original["fired_rules"]) or "Tidak ada")
            st.write("Rekomendasi:", len(original["recommendations"]))
        with right:
            st.subheader("Sesudah")
            status_box(st, changed["status"])
            st.write("Aturan:", ", ".join(changed["fired_rules"]) or "Tidak ada")
            st.write("Rekomendasi:", len(changed["recommendations"]))
        before = {i["key"] for i in original["recommendations"]}
        after = {i["key"] for i in changed["recommendations"]}
        st.subheader("Perubahan rekomendasi")
        st.write("**Rekomendasi baru:**", ", ".join(ACTIONS[k][0] for k in ACTIONS if k in after - before) or "Tidak ada")
        st.write("**Rekomendasi yang tidak lagi aktif:**", ", ".join(ACTIONS[k][0] for k in ACTIONS if k in before - after) or "Tidak ada")


def knowledge_page(st) -> None:
    st.title("📚 Knowledge Base")
    st.write("Daftar aturan yang dipakai mesin forward chaining. Pada versi satu file, aturan disimpan langsung dalam daftar `RULES`.")
    for rule in RULES:
        with st.expander(f"{rule['id']} — {rule['name']}"):
            st.write("**IF:**")
            for fact, val in rule["if"].items():
                st.write(f"• {FACT_LABELS.get(fact, fact)} = {str(val).upper()}")
            st.write("**THEN:**")
            for fact, val in rule["then"].items():
                st.write(f"• {FACT_LABELS.get(fact, fact)} = {str(val).upper()}")
            st.write("**Alasan:**", rule["because"])
    st.divider()
    st.subheader("Ambang batas yang digunakan")
    st.json(THRESHOLDS)
    st.warning("Angka batas di atas hanya untuk simulasi. Untuk tugas akhir, cantumkan literatur, sumber ahli, atau kebijakan perusahaan sebagai dasar aturan.")


def main() -> None:
    # Import di sini membuat fungsi engine dapat diuji tanpa instalasi Streamlit.
    import streamlit as st

    st.set_page_config(page_title="StockWise | Sistem Pakar", page_icon="📦", layout="wide")
    st.markdown("""
        <style>
        .block-container {max-width: 1150px; padding-top: 1.7rem;}
        h1, h2 {letter-spacing: -.02em;}
        div[data-testid="stMetric"] {padding: 12px; border: 1px solid #d9e4df; border-radius: 10px;}
        </style>
    """, unsafe_allow_html=True)

    with st.sidebar:
        st.title("📦 STOCKWISE")
        st.caption("Raw Material Procurement Expert System")
        page = st.radio("Menu", [
            "Dashboard", "Analisis Persediaan", "Penjelasan AI", "Simulasi What-if", "Knowledge Base"
        ])
        st.divider()
        st.caption("Metode: Forward Chaining · 10 aturan")
        st.caption("Data contoh: bahan baku Polypropylene (PP)")

    if page == "Dashboard":
        dashboard_page(st)
    elif page == "Analisis Persediaan":
        analysis_page(st)
    elif page == "Penjelasan AI":
        explanation_page(st)
    elif page == "Simulasi What-if":
        simulation_page(st)
    else:
        knowledge_page(st)


def run_stockwise() -> None:
    """Jalankan dari `python app.py` atau dari `streamlit run app.py`.

    Otomatis menginstal Streamlit hanya jika belum terpasang di interpreter ini.
    Perintah pip dijalankan melalui subprocess, bukan ditulis sebagai sintaks Python.
    """
    import importlib.util
    from pathlib import Path
    import subprocess
    import sys

    if importlib.util.find_spec("streamlit") is None:
        print("[StockWise] Streamlit belum terinstal. Mencoba menginstal otomatis...")
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "streamlit"],
                check=True,
            )
        except subprocess.CalledProcessError:
            print("\n[StockWise] Instalasi Streamlit gagal. Periksa koneksi internet dan pip.")
            print(f"Jalankan di TERMINAL: \"{sys.executable}\" -m pip install streamlit")
            sys.exit(1)

    # Saat dijalankan lewat server Streamlit, panggil antarmuka secara langsung.
    # Saat dijalankan lewat tombol Run Python File / `python app.py`, mulai server.
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        running_under_streamlit = get_script_run_ctx(suppress_warning=True) is not None
    except ImportError:
        # Jika versi Streamlit yang dipasang tak memiliki API ini, minta cara manual.
        print("[StockWise] Jalankan lewat TERMINAL: python -m streamlit run app.py")
        sys.exit(1)

    if running_under_streamlit:
        main()
    else:
        print("[StockWise] Menjalankan website... buka http://localhost:8501")
        try:
            subprocess.run(
                [sys.executable, "-m", "streamlit", "run", str(Path(__file__).resolve())],
                check=True,
            )
        except KeyboardInterrupt:
            print("\n[StockWise] Server dihentikan.")
        except subprocess.CalledProcessError:
            print("[StockWise] Server gagal dimulai; lihat pesan di atas.")
            sys.exit(1)


if __name__ == "__main__":
    run_stockwise()
