import os
import io
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from datetime import datetime
from sqlalchemy import text

app = Flask(__name__)

# --- KONFIGURASI DATABASE ---
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:@localhost/asira_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'asira_super_secret_key'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 

db = SQLAlchemy(app)

# ==========================================
# MODEL DATABASE
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
    data_gambar = db.Column(db.LargeBinary(length=16777215)) 
    mimetype = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.now)

    @property
    def img_url(self):
        return url_for('tampilkan_gambar', tipe='cover', id=self.id)

# --- TABEL KHUSUS TWIBBON ---
class AssetTwibbon(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    judul = db.Column(db.String(100))
    data_gambar = db.Column(db.LargeBinary(length=16777215)) 
    mimetype = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.now)

    @property
    def img_url(self):
        return url_for('tampilkan_gambar', tipe='twibbon', id=self.id)

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

    # [MODIFIED] Tambahan untuk API Mobile
    def to_dict(self):
        login_code = f"{self.no_hp[-4:]}ASR" if self.no_hp and len(self.no_hp) >= 4 else None
        return {
            'id': self.id,
            'nama': self.nama,
            'peran': self.peran,
            'no_hp': self.no_hp,
            'status': self.status,
            'login_code': login_code
        }

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
# ROUTES WEB ADMIN
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
    
    assets_cover = AssetCover.query.order_by(AssetCover.id.desc()).all()
    assets_twibbon = AssetTwibbon.query.order_by(AssetTwibbon.id.desc()).all()
    
    return render_template('design.html', active_page='design', config=config, assets_cover=assets_cover, assets_twibbon=assets_twibbon)

@app.route('/img_render/<tipe>/<int:id>')
def tampilkan_gambar(tipe, id):
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
    return render_template('rundown.html', active_page='rundown', items=Rundown.query.order_by(Rundown.waktu).all())

@app.route('/gifts', methods=['GET', 'POST'])
def gifts():
    if request.method == 'POST':
        nama = request.form.get('nama_pengirim') # Perbaikan: menyesuaikan form HTML (sebelumnya 'nama')
        no_amplop = request.form.get('no_amplop')
        jenis_hadiah = request.form.get('jenis', 'Amplop') 

        if nama and no_amplop:
            new_gift = Hadiah(
                no_amplop=no_amplop,
                nama_pengirim=nama,
                jenis=jenis_hadiah,
                keterangan="Input Cepat Meja Penerima",
                waktu_terima=datetime.now()
            )
            db.session.add(new_gift)
            db.session.commit()
            flash(f"Data hadiah dari {nama} berhasil disimpan!")
        else:
            flash("Gagal menyimpan: Nama dan Nomor Amplop harus diisi.")
            
        return redirect(url_for('gifts'))

    hadiah_list = Hadiah.query.order_by(Hadiah.id.desc()).all()
    total_hadiah = Hadiah.query.count()
    
    return render_template('gifts.html', active_page='gifts', hadiah=hadiah_list, total=total_hadiah)

@app.route('/crew', methods=['GET', 'POST'])
def crew():
    if request.method == 'POST':
        db.session.add(Crew(nama=request.form['nama'], peran=request.form['peran'], no_hp=request.form['no_hp']))
        db.session.commit()
        return redirect(url_for('crew'))
    return render_template('crew.html', active_page='crew', crew=Crew.query.all())

@app.route('/edit_crew/<int:id>', methods=['POST'])
def edit_crew(id):
    try:
        c = Crew.query.get_or_404(id)
        c.nama = request.form.get('nama')
        c.peran = request.form.get('peran')
        c.no_hp = request.form.get('no_hp')
        c.status = request.form.get('status')
        db.session.commit()
        flash(f"Data crew {c.nama} berhasil diperbarui.")
    except Exception as e:
        db.session.rollback()
        flash(f"Gagal memperbarui data: {str(e)}")
    return redirect(url_for('crew'))

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

@app.route('/tambah_rundown', methods=['POST'])
def tambah_rundown():
    waktu = request.form.get('waktu')
    judul = request.form.get('judul')
    deskripsi = request.form.get('deskripsi')
    pic = request.form.get('pic')
    status = request.form.get('status')
    
    new_item = Rundown(waktu=waktu, judul=judul, deskripsi=deskripsi, pic=pic, status=status)
    db.session.add(new_item)
    db.session.commit()
    flash("Jadwal acara berhasil ditambahkan.")
    return redirect(url_for('rundown'))

@app.route('/edit_rundown/<int:id>', methods=['POST'])
def edit_rundown(id):
    try:
        item = Rundown.query.get_or_404(id)
        item.waktu = request.form.get('waktu')
        item.judul = request.form.get('judul')
        item.deskripsi = request.form.get('deskripsi')
        item.pic = request.form.get('pic')
        item.status = request.form.get('status')
        db.session.commit()
        flash("Jadwal diperbarui.")
    except Exception as e:
        db.session.rollback()
        flash(f"Error: {str(e)}")
    return redirect(url_for('rundown'))

@app.route('/hapus_rundown/<int:id>')
def hapus_rundown(id):
    try:
        item = Rundown.query.get_or_404(id)
        db.session.delete(item)
        db.session.commit()
        if Rundown.query.count() == 0:
            db.session.execute(text("ALTER TABLE rundown AUTO_INCREMENT = 1"))
            db.session.commit()
        flash("Jadwal dihapus.")
    except Exception as e:
        db.session.rollback()
        flash(f"Error: {str(e)}")
    return redirect(url_for('rundown'))

@app.route('/scan')
def scan_page():
    return render_template('scan.html', active_page='scan')

@app.route('/api/process-scan', methods=['POST'])
def process_scan_api():
    data = request.get_json()
    barcode_value = data.get('barcode')

    if barcode_value:
        flash(f"Barcode '{barcode_value}' berhasil diproses!", "success")
        return {'status': 'success', 'message': f'Data {barcode_value} diproses.'}
    else:
        flash("Gagal memproses barcode.", "error")
        return {'status': 'error', 'message': 'Tidak ada data barcode.'}, 400
    
@app.route('/invitation/<slug>')
def view_invitation(slug):
    # Logika untuk mengambil config invitation (sementara menggunakan dummy/default)
    config = DesignConfig.query.first()
    if not config:
        config = DesignConfig() # Default
    
    # JIKA ada parameter di URL (berasal dari tombol preview), tindih data DB
    if request.args.get('preview'):
        config.judul_mempelai = request.args.get('nama')
        config.tanggal_acara = request.args.get('tanggal')
        config.tema_warna = request.args.get('tema')
    
    return render_template('invitation.html', config=config)

# ==========================================
# API MOBILE SERVICES (CREW & ROLES)
# ==========================================

# 1. API LOGIN CREW
@app.route('/api/mobile/crew/login', methods=['POST'])
def api_crew_login():
    data = request.get_json()
    kode_akses = data.get('kode_akses') # Input dari mobile app

    if not kode_akses:
        return jsonify({'status': 'error', 'message': 'Kode akses harus diisi'}), 400

    # Ambil semua crew untuk dicocokkan kodenya
    all_crew = Crew.query.all()
    user_found = None

    for c in all_crew:
        if c.no_hp and len(c.no_hp) >= 4:
            generated_code = f"{c.no_hp[-4:]}ASR"
            if generated_code == kode_akses:
                user_found = c
                break
    
    if user_found:
        if user_found.status != 'Active':
             return jsonify({'status': 'error', 'message': 'Akun Anda sedang dinonaktifkan (Offline).'}), 403

        return jsonify({
            'status': 'success',
            'message': 'Login berhasil',
            'data': user_found.to_dict()
        })
    else:
        return jsonify({'status': 'error', 'message': 'Kode akses tidak valid'}), 401

# 2. GET LIST CREW
@app.route('/api/mobile/crew', methods=['GET'])
def api_get_crew():
    crews = Crew.query.all()
    return jsonify({
        'status': 'success',
        'total': len(crews),
        'data': [c.to_dict() for c in crews]
    })

# 3. GET DETAIL CREW
@app.route('/api/mobile/crew/<int:id>', methods=['GET'])
def api_get_crew_detail(id):
    c = Crew.query.get(id)
    if not c:
        return jsonify({'status': 'error', 'message': 'Crew tidak ditemukan'}), 404
    return jsonify({'status': 'success', 'data': c.to_dict()})

# 4. TAMBAH CREW BARU (POST)
@app.route('/api/mobile/crew', methods=['POST'])
def api_add_crew():
    data = request.get_json()
    
    if not data.get('nama') or not data.get('no_hp'):
        return jsonify({'status': 'error', 'message': 'Nama dan No HP wajib diisi'}), 400

    try:
        new_crew = Crew(
            nama=data.get('nama'),
            peran=data.get('peran', 'Usher'),
            no_hp=data.get('no_hp'),
            status='Active'
        )
        db.session.add(new_crew)
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Crew berhasil ditambahkan', 'data': new_crew.to_dict()}), 201
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# 5. EDIT DATA CREW (PUT)
@app.route('/api/mobile/crew/<int:id>', methods=['PUT'])
def api_edit_crew(id):
    c = Crew.query.get(id)
    if not c:
        return jsonify({'status': 'error', 'message': 'Crew tidak ditemukan'}), 404
    
    data = request.get_json()
    try:
        if 'nama' in data: c.nama = data['nama']
        if 'peran' in data: c.peran = data['peran']
        if 'no_hp' in data: c.no_hp = data['no_hp']
        if 'status' in data: c.status = data['status'] # Active / Offline
        
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Data crew diperbarui', 'data': c.to_dict()})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# 6. HAPUS CREW (DELETE)
@app.route('/api/mobile/crew/<int:id>', methods=['DELETE'])
def api_delete_crew(id):
    c = Crew.query.get(id)
    if not c:
        return jsonify({'status': 'error', 'message': 'Crew tidak ditemukan'}), 404
    
    try:
        db.session.delete(c)
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Crew berhasil dihapus'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# 7. BULK ACTION (Active All / Offline All)
@app.route('/api/mobile/crew/status/all', methods=['POST'])
def api_bulk_status_crew():
    data = request.get_json()
    target_status = data.get('status') # 'Active' atau 'Offline'
    
    if target_status not in ['Active', 'Offline']:
        return jsonify({'status': 'error', 'message': 'Status tidak valid. Gunakan Active atau Offline'}), 400

    try:
        crews = Crew.query.all()
        for c in crews:
            c.status = target_status
        db.session.commit()
        return jsonify({'status': 'success', 'message': f'Semua crew diubah menjadi {target_status}'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    
@app.route('/api/mobile/login-phone', methods=['POST'])
def api_login_phone():
    try:
        data = request.get_json()
        phone_number = data.get('phone_number')

        if not phone_number:
            return jsonify({'status': 'error', 'message': 'Nomor HP wajib diisi'}), 400

        # Cari crew berdasarkan no_hp
        # Pastikan kolom no_hp di database formatnya sama (misal 0812 vs 62812)
        user = Crew.query.filter_by(no_hp=phone_number).first()

        if user:
            if user.status != 'Active':
                 return jsonify({'status': 'error', 'message': 'Akun dinonaktifkan.'}), 403

            return jsonify({
                'status': 'success',
                'message': 'Login Berhasil',
                'data': user.to_dict()
            })
        else:
            return jsonify({
                'status': 'error', 
                'message': 'Nomor HP tidak ditemukan.'
            }), 404

    except Exception as e:
        print(f"Error Login: {e}")
        return jsonify({'status': 'error', 'message': f'Server Error: {str(e)}'}), 500

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)