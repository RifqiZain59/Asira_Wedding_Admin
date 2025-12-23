import os
import io
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from datetime import datetime

app = Flask(__name__)

# --- KONFIGURASI DATABASE ---
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:@localhost/asira_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'asira_super_secret_key'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 

db = SQLAlchemy(app)

# ==========================================
# MODEL DATABASE (DIPISAH)
# ==========================================

class DesignConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    judul_mempelai = db.Column(db.String(100), default="Putra & Putri")
    tanggal_acara = db.Column(db.String(100), default="Minggu, 12 Oktober 2025")
    tema_warna = db.Column(db.String(20), default="charcoal")

# --- TABEL KHUSUS COVER ---
class AssetCover(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    judul = db.Column(db.String(100))
    # Kolom BLOB untuk Cover
    data_gambar = db.Column(db.LargeBinary(length=16777215)) 
    mimetype = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.now)

    @property
    def img_url(self):
        # Mengarah ke endpoint render dengan tipe 'cover'
        return url_for('tampilkan_gambar', tipe='cover', id=self.id)

# --- TABEL KHUSUS TWIBBON ---
class AssetTwibbon(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    judul = db.Column(db.String(100))
    # Kolom BLOB untuk Twibbon
    data_gambar = db.Column(db.LargeBinary(length=16777215)) 
    mimetype = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.now)

    @property
    def img_url(self):
        # Mengarah ke endpoint render dengan tipe 'twibbon'
        return url_for('tampilkan_gambar', tipe='twibbon', id=self.id)

# --- MODEL LAINNYA (Tamu, dll) ---
class Tamu(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nama = db.Column(db.String(100), nullable=False)
    kategori = db.Column(db.String(50), default='Reguler')
    no_hp = db.Column(db.String(20))
    meja = db.Column(db.String(10))
    status_rsvp = db.Column(db.String(20), default='Pending')
    waktu_checkin = db.Column(db.DateTime, nullable=True)

class Rundown(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    waktu = db.Column(db.String(10))
    judul = db.Column(db.String(100))
    deskripsi = db.Column(db.Text)
    pic = db.Column(db.String(50))
    status = db.Column(db.String(20), default='Upcoming') 

class Hadiah(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    no_amplop = db.Column(db.String(20))
    nama_pengirim = db.Column(db.String(100))
    jenis = db.Column(db.String(50))
    keterangan = db.Column(db.String(200))
    waktu_terima = db.Column(db.DateTime, default=datetime.now)

class Crew(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nama = db.Column(db.String(100))
    peran = db.Column(db.String(50))
    no_hp = db.Column(db.String(20))
    status = db.Column(db.String(20), default='Active')

class Lokasi(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nama_tempat = db.Column(db.String(100))
    alamat = db.Column(db.Text)
    link_gmaps = db.Column(db.String(255))
    kategori = db.Column(db.String(50))

class MenuMakanan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nama_menu = db.Column(db.String(100))
    jenis = db.Column(db.String(50))
    deskripsi = db.Column(db.String(200))
    porsi = db.Column(db.Integer)

# ==========================================
# ROUTES
# ==========================================

@app.route('/')
def dashboard():
    total_tamu = Tamu.query.count()
    hadir = Tamu.query.filter_by(status_rsvp='Hadir').count()
    vip = Tamu.query.filter(Tamu.kategori.in_(['VIP', 'VVIP'])).count()
    latest = Tamu.query.filter(Tamu.waktu_checkin.isnot(None)).order_by(Tamu.waktu_checkin.desc()).limit(5).all()
    return render_template('dashboard.html', active_page='dashboard', total=total_tamu, hadir=hadir, vip=vip, latest=latest)

@app.route('/design')
def design():
    config = DesignConfig.query.first()
    if not config:
        config = DesignConfig()
        db.session.add(config)
        db.session.commit()
    
    # Ambil dari tabel terpisah
    assets_cover = AssetCover.query.order_by(AssetCover.id.desc()).all()
    assets_twibbon = AssetTwibbon.query.order_by(AssetTwibbon.id.desc()).all()
    
    return render_template('design.html', active_page='design', config=config, assets_cover=assets_cover, assets_twibbon=assets_twibbon)

# ROUTE RENDER GAMBAR (Updated untuk support 2 tabel)
@app.route('/img_render/<tipe>/<int:id>')
def tampilkan_gambar(tipe, id):
    # Cek tipe untuk menentukan tabel mana yang diambil
    if tipe == 'cover':
        asset = AssetCover.query.get_or_404(id)
    elif tipe == 'twibbon':
        asset = AssetTwibbon.query.get_or_404(id)
    else:
        return "Tipe tidak valid", 400

    if not asset.data_gambar:
        return "Gambar Kosong", 404
    
    return send_file(
        io.BytesIO(asset.data_gambar),
        mimetype=asset.mimetype,
        as_attachment=False,
        download_name=asset.judul
    )

@app.route('/api/add_asset', methods=['POST'])
def add_asset():
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'Tidak ada file'}), 400
    
    file = request.files['file']
    tipe = request.form.get('tipe') # cover atau twibbon
    
    if file.filename == '':
        return jsonify({'status': 'error', 'message': 'Nama file kosong'}), 400
        
    if file:
        try:
            filename = secure_filename(file.filename)
            file_data = file.read()
            
            new_id = None
            
            # Pisahkan logika simpan berdasarkan tipe
            if tipe == 'cover':
                new_asset = AssetCover(
                    judul=filename,
                    data_gambar=file_data,
                    mimetype=file.mimetype,
                    created_at=datetime.now()
                )
                db.session.add(new_asset)
                db.session.commit()
                new_id = new_asset.id
                
            elif tipe == 'twibbon':
                new_asset = AssetTwibbon(
                    judul=filename,
                    data_gambar=file_data,
                    mimetype=file.mimetype,
                    created_at=datetime.now()
                )
                db.session.add(new_asset)
                db.session.commit()
                new_id = new_asset.id
            
            else:
                return jsonify({'status': 'error', 'message': 'Tipe aset tidak valid'}), 400
            
            return jsonify({
                'status': 'success', 
                'message': 'Upload berhasil',
                'img_url': url_for('tampilkan_gambar', tipe=tipe, id=new_id)
            })

        except Exception as e:
            print(f"Error: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500
            
    return jsonify({'status': 'error', 'message': 'Gagal upload'}), 500

@app.route('/api/save_design_config', methods=['POST'])
def save_design_config():
    data = request.json
    config = DesignConfig.query.first()
    if not config:
        config = DesignConfig()
        db.session.add(config)
    config.judul_mempelai = data.get('judul_mempelai')
    config.tanggal_acara = data.get('tanggal_acara')
    config.tema_warna = data.get('tema_warna')
    db.session.commit()
    return jsonify({'status': 'success', 'message': 'Konfigurasi tersimpan'})

# Update Delete untuk menerima TIPE agar tahu hapus dari tabel mana
@app.route('/api/delete_asset/<tipe>/<int:id>', methods=['POST'])
def delete_asset(tipe, id):
    try:
        if tipe == 'cover':
            asset = AssetCover.query.get_or_404(id)
            db.session.delete(asset)
        elif tipe == 'twibbon':
            asset = AssetTwibbon.query.get_or_404(id)
            db.session.delete(asset)
        else:
            return jsonify({'status': 'error', 'message': 'Tipe salah'}), 400
            
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Aset dihapus'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# --- ROUTES FITUR LAIN ---
@app.route('/tamu')
def tamu():
    return render_template('tamu.html', active_page='tamu', tamu=Tamu.query.order_by(Tamu.id.desc()).all())

@app.route('/tambah_tamu', methods=['POST'])
def tambah_tamu():
    db.session.add(Tamu(nama=request.form['nama'], kategori=request.form['kategori'], no_hp=request.form['no_hp'], meja=request.form['meja']))
    db.session.commit()
    flash("Tamu berhasil ditambahkan.")
    return redirect(url_for('tamu'))

@app.route('/edit_tamu/<int:id>', methods=['POST'])
def edit_tamu(id):
    t = Tamu.query.get_or_404(id)
    t.nama = request.form['nama']
    t.kategori = request.form['kategori']
    t.meja = request.form['meja']
    t.no_hp = request.form['no_hp']
    db.session.commit()
    flash("Data tamu diperbarui.")
    return redirect(url_for('tamu'))

@app.route('/checkin/<int:id>')
def checkin(id):
    t = Tamu.query.get_or_404(id)
    t.waktu_checkin = datetime.now()
    t.status_rsvp = 'Hadir'
    db.session.commit()
    return redirect(url_for('tamu'))

@app.route('/hapus_tamu/<int:id>')
def hapus_tamu(id):
    db.session.delete(Tamu.query.get_or_404(id))
    db.session.commit()
    flash("Data tamu dihapus.")
    return redirect(url_for('tamu'))

@app.route('/rundown')
def rundown():
    if Rundown.query.count() == 0:
        db.session.add(Rundown(waktu="18:30", judul="Registrasi", deskripsi="Area Foyer", pic="Usher"))
        db.session.commit()
    return render_template('rundown.html', active_page='rundown', items=Rundown.query.order_by(Rundown.waktu).all())

@app.route('/gifts', methods=['GET', 'POST'])
def gifts():
    if request.method == 'POST':
        db.session.add(Hadiah(no_amplop=request.form['no_amplop'], nama_pengirim=request.form['nama'], jenis=request.form['jenis'], keterangan="Input Manual"))
        db.session.commit()
        return redirect(url_for('gifts'))
    return render_template('gifts.html', active_page='gifts', hadiah=Hadiah.query.order_by(Hadiah.id.desc()).all(), total=Hadiah.query.count())

@app.route('/crew', methods=['GET', 'POST'])
def crew():
    if request.method == 'POST':
        db.session.add(Crew(nama=request.form['nama'], peran=request.form['peran'], no_hp=request.form['no_hp']))
        db.session.commit()
        return redirect(url_for('crew'))
    return render_template('crew.html', active_page='crew', crew=Crew.query.all())

@app.route('/hapus_crew/<int:id>')
def hapus_crew(id):
    db.session.delete(Crew.query.get_or_404(id))
    db.session.commit()
    return redirect(url_for('crew'))

@app.route('/settings')
def settings():
    return render_template('settings.html', active_page='settings')

@app.route('/maps')
def maps():
    if Lokasi.query.count() == 0:
        db.session.add(Lokasi(nama_tempat="Grand Ballroom", alamat="Jl. Jendral Sudirman", link_gmaps="#", kategori="Resepsi"))
        db.session.commit()
    return render_template('maps.html', active_page='maps', lokasi=Lokasi.query.all())

@app.route('/tambah_lokasi', methods=['POST'])
def tambah_lokasi():
    db.session.add(Lokasi(nama_tempat=request.form['nama_tempat'], alamat=request.form['alamat'], link_gmaps=request.form['link_gmaps'], kategori=request.form['kategori']))
    db.session.commit()
    flash("Lokasi berhasil ditambahkan.")
    return redirect(url_for('maps'))

@app.route('/makanan')
def makanan():
    if MenuMakanan.query.count() == 0:
        db.session.add(MenuMakanan(nama_menu="Nasi Goreng", jenis="Buffet", deskripsi="Spesial", porsi=500))
        db.session.commit()
    return render_template('makanan.html', active_page='makanan', makanan=MenuMakanan.query.all())

@app.route('/tambah_makanan', methods=['POST'])
def tambah_makanan():
    db.session.add(MenuMakanan(nama_menu=request.form['nama_menu'], jenis=request.form['jenis'], deskripsi=request.form['deskripsi'], porsi=request.form['porsi']))
    db.session.commit()
    flash("Menu makanan berhasil ditambahkan.")
    return redirect(url_for('makanan'))

@app.route('/crew_active_all')
def crew_active_all():
    crews = Crew.query.all()
    for c in crews:
        c.status = 'Active'
    db.session.commit()
    flash("Semua akses crew telah diaktifkan kembali.")
    return redirect(url_for('crew'))

@app.route('/crew_offline_all')
def crew_offline_all():
    crews = Crew.query.all()
    for c in crews:
        c.status = 'Offline'
    db.session.commit()
    flash("Semua akses crew telah dinonaktifkan.")
    return redirect(url_for('crew'))

if __name__ == "__main__":
    with app.app_context():
        # Karena model berubah, Anda harus menghapus tabel lama di database manager
        # agar tabel 'asset_cover' dan 'asset_twibbon' baru bisa dibuat.
        db.create_all()
    app.run(debug=True)