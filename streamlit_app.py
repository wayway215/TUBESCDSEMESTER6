import streamlit as st
import firebase_admin
from firebase_admin import credentials, db
import time
import altair as alt
import pandas as pd

# ------------------ Inisialisasi Firebase ------------------ #
cred = credentials.Certificate("tubescd-firebase-adminsdk-fbsvc-9bc24f8fe2.json")
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://tubescd-default-rtdb.asia-southeast1.firebasedatabase.app/'
    })

st.set_page_config(page_title="Dashboard Kebun Buah Naga", layout="wide")
st.title("🌿 Dashboard Monitoring Kebun Naga")

# ------------------ Riwayat Perubahan Umur Tanaman ------------------ #
with st.expander("📜 Riwayat Perubahan Umur Tanaman"):
    log_ref = db.reference("log_umur")
    log_data = log_ref.get() or {}
    if log_data:
        log_df = pd.DataFrame.from_dict(log_data, orient="index")
        log_df = log_df.sort_values(by="timestamp", ascending=False)
        st.dataframe(log_df, use_container_width=True)

        st.subheader("📉 Grafik Perubahan Umur Tanaman")
        log_df["timestamp"] = pd.to_datetime(log_df["timestamp"])
        log_df["umur"] = pd.to_numeric(log_df["umur"], errors="coerce")
        umur_chart = alt.Chart(log_df).mark_line(point=True).encode(
            x="timestamp:T",
            y=alt.Y("umur:Q", title="Umur (bulan)")
        ).properties(height=300)
        st.altair_chart(umur_chart, use_container_width=True)
    else:
        st.info("Belum ada riwayat perubahan umur tanaman.")

# ------------------ Looping Update Realtime ------------------ #
pemupukan_ref = db.reference("pemupukan")
placeholder = st.empty()

# Inisialisasi DataFrame kosong untuk grafik
history = pd.DataFrame(columns=["timestamp", "moisture1", "moisture2", "moisture3", "lux"])
# Gunakan file CSV sebelumnya jika tersedia
try:
    history = pd.read_csv("/mnt/data/history_log.csv")
    history["timestamp"] = pd.to_datetime(history["timestamp"])
except:
    pass


refresh = st.button("🔄 Refresh Sekarang", key="refresh_button")

def render_dashboard():
    global history
    with placeholder.container():
        sensor_ref = db.reference("sensor")
        status_ref = db.reference("status")
        waktu_ref = db.reference("waktu")
        kontrol_ref = db.reference("kontrol")

        sensor_data = sensor_ref.get() or {}
        status_data = status_ref.get() or {}
        waktu_data = waktu_ref.get() or {}
        kontrol_data = kontrol_ref.get() or {}

        timestamp = pd.Timestamp.now()
        row = {
            "timestamp": timestamp,
            "moisture1": sensor_data.get("moisture1", 0),
            "moisture2": sensor_data.get("moisture2", 0),
            "moisture3": sensor_data.get("moisture3", 0),
            "lux": sensor_data.get("lux", 0)
        }
        history = pd.concat([history, pd.DataFrame([row])], ignore_index=True).tail(50)

        st.subheader("📊 Data Sensor Saat Ini")

        # 🚨 Peringatan jika kelembapan terlalu rendah
        if any(sensor_data.get(f"moisture{i}", 100) < 40 for i in range(1, 4)):
            st.error("🚨 Kelembapan tanah terlalu rendah! Segera siram tanaman!")

        # ⏳ Hitung mundur waktu pemupukan berikutnya (setiap 30 hari dari umur terakhir diubah)
        try:
            last_log = max(log_data.values(), key=lambda x: x.get("timestamp", ""))
            last_time = pd.to_datetime(last_log["timestamp"])
            next_fertilize = last_time + pd.Timedelta(days=30)
            countdown = next_fertilize - pd.Timestamp.now()
            if countdown.days >= 0:
                st.warning(f"⏳ Pemupukan berikutnya dalam: {countdown.days} hari")
            else:
                st.warning("📅 Jadwal pemupukan sudah lewat! Segera lakukan pemupukan!")
        except Exception:
            st.info("ℹ️ Belum ada jadwal pemupukan tercatat.")

        pemupukan_data = pemupukan_ref.get() or {}
        with st.form(key="pemupukan_form", clear_on_submit=False):
            input_umur = st.number_input("Input Umur Tanaman (bulan)", min_value=0, max_value=12, step=1, value=pemupukan_data.get("umur", 0), key="input_umur_fixed")
            submit_umur = st.form_submit_button("📤 Update Umur Tanaman")
            if submit_umur:
                log_ref = db.reference("log_umur")
                log_ref.push({
                    "timestamp": str(pd.Timestamp.now()),
                    "umur": input_umur
                })

                jenis, dosis, ket = '-', '-', '-'
                if input_umur == 0:
                    jenis, dosis, ket = 'TSP, KCL, ZA', '60g, 60g, 20g', 'Pupuk dasar'
                elif input_umur <= 5:
                    jenis, dosis, ket = 'NPK Mutiara', '1 sdm makan', 'Per tanaman'
                elif input_umur in [7, 8]:
                    jenis, dosis, ket = 'TSP, KCL, Grow more', '2 sdm, 2 sdm, 1 sdm + 5L air', 'Dicampur & disiram di tiang'
                elif input_umur in [9, 10]:
                    jenis, dosis, ket = 'Grow more', '1 sdm + 5L air', 'Disiram di tiang'
                elif input_umur == 11:
                    jenis, dosis, ket = '-', '-', 'Awal berbuah'
                elif input_umur == 12:
                    jenis, dosis, ket = '-', '-', 'Sedang berbuah'
                pemupukan_ref.update({
                    "umur": input_umur,
                    "jenis_pupuk": jenis,
                    "dosis": dosis,
                    "keterangan": ket
                })
                st.success(f"✅ Umur diperbarui dan data pemupukan disesuaikan untuk umur {input_umur} bulan")

                if jenis == '-' and dosis == '-':
                    st.warning("⚠️ Umur ini belum memiliki jenis pupuk yang ditentukan.")
        pemupukan_data = pemupukan_ref.get() or {}
        st.markdown("""
        ### 🧪 Data Pemupukan
        - **Umur Tanaman:** {umur} bulan
        - **Jenis Pupuk:** {jenis}
        - **Dosis:** {dosis}
        - **Keterangan:** {ket}
        """.format(
            umur=pemupukan_data.get("umur", "-"),
            jenis=pemupukan_data.get("jenis_pupuk", "-"),
            dosis=pemupukan_data.get("dosis", "-"),
            ket=pemupukan_data.get("keterangan", "-")
        ))
        col1, col2 = st.columns(2)

        with col1:
            st.metric("Moisture 1", f"{sensor_data.get('moisture1', '-')} %")
            st.metric("Moisture 2", f"{sensor_data.get('moisture2', '-')} %")
            st.metric("Moisture 3", f"{sensor_data.get('moisture3', '-')} %")
            st.metric("Lux", f"{sensor_data.get('lux', '-')} lx")

        with col2:
            try:
                jarak = float(sensor_data.get('water_level_cm', 0))
                tinggi_tandon = 56.0  # cm
                kapasitas_persen = max(0, min(100, int((tinggi_tandon - jarak) / tinggi_tandon * 100)))
                st.metric("Kapasitas Air", f"{kapasitas_persen} %")
            except:
                st.metric("Kapasitas Air", "-")
            status_lampu = status_data.get("lampu", "-")
            status_color_lampu = "green" if status_lampu == "ON" else ("red" if status_lampu == "OFF" else "gray")
            st.markdown(f"<div style='background-color:{status_color_lampu};padding:10px;border-radius:5px;color:white'>💡 Status Lampu: <b>{status_lampu}</b></div>", unsafe_allow_html=True)
            status_pompa = status_data.get("pompa", "-")
            status_color_pompa = "green" if status_pompa == "ON" else ("red" if status_pompa == "OFF" else "gray")
            st.markdown(f"<div style='background-color:{status_color_pompa};padding:10px;border-radius:5px;color:white'>🚿 Status Pompa: <b>{status_pompa}</b></div>", unsafe_allow_html=True)
            st.metric("Waktu RTC", waktu_data.get("rtc", "-"))

        

        st.subheader("🛠️ Kontrol Manual")
        with st.form(key="kontrol_form"):
            mode_lampu = st.selectbox("Mode Lampu", [1, 2], format_func=lambda x: "Manual" if x == 1 else "Otomatis", key="mode_lampu")
            mode_pompa = st.selectbox("Mode Pompa", [1, 2], format_func=lambda x: "Manual" if x == 1 else "Otomatis", key="mode_pompa")

            manual_lampu = st.radio("Kondisi Lampu (Manual)", ["OFF", "ON"], key="lampu") if mode_lampu == 1 else None
            manual_pompa = st.radio("Kondisi Pompa (Manual)", ["OFF", "ON"], key="pompa") if mode_pompa == 1 else None

            submit = st.form_submit_button("💾 Kirim ke Firebase")

            if submit:
                kontrol_ref.update({
                    "lampu": mode_lampu,
                    "pompa": mode_pompa
                })
                if mode_lampu == 1:
                    db.reference("manual/lampu").set(1 if manual_lampu == "ON" else 0)
                if mode_pompa == 1:
                    db.reference("manual/pompa").set(1 if manual_pompa == "ON" else 0)
                st.success("✅ Data berhasil diperbarui ke Firebase!")

        history.to_csv("history_log.csv", index=False)

# Jalankan dashboard sekali dan gunakan tombol untuk refresh manual
render_dashboard()

