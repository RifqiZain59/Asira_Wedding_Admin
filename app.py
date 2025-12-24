import os
import io
import random
import string
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from datetime import datetime
from sqlalchemy import text

app = Flask(__name__)

# --- KONFIGURASI DATABASE ---
# Sesuaikan dengan config database lokal Anda
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:@localhost/asira_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'asira_super_secret_key'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 

db = SQLAlchemy(app)

# ==========================================
# MODEL DATABASE (DENGAN TO_DICT UNTUK API)
# ==========================================

class DesignConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    judul_mempelai = db.Column(db.String(100), default="Putra & Putri")
    tanggal_acara = db.Column(db.String(100), default="Minggu, 12 Oktober 2025")
    tema_warna = db.Column(db.String(20), default="charcoal")

class AssetCover(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    judul = db.Column(db.String(100))
    data_gambar = db.Column(db.LargeBinary(length=16777215)) 
    mimetype = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.now)

    @property
    def img_url(self):
        return url_for('tampilkan_gambar', tipe='cover', id=self.id)

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

    def to_dict(self):
        return {
            'id': self.id,
            'nama': self.nama,
            'kategori': self.kategori,
            'no_hp': self.no_hp,
            'meja': self.meja,
            'status_rsvp': self.status_rsvp,
            'waktu_checkin': self.waktu_checkin.isoformat() if self.waktu_checkin else None
        }

class Rundown(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    waktu = db.Column(db.String(10))
    judul = db.Column(db.String(100))
    deskripsi = db.Column(db.Text)
    pic = db.Column(db.String(50))
    status = db.Column(db.String(20), default='Upcoming') 

    def to_dict(self):
        return {
            'id': self.id,
            'waktu': self.waktu,
            'judul': self.judul,
            'deskripsi': self.deskripsi,
            'pic': self.pic,
            'status': self.status
        }

class Hadiah(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    no_amplop = db.Column(db.String(20))
    nama_pengirim = db.Column(db.String(100))
    jenis = db.Column(db.String(50))
    keterangan = db.Column(db.String(200))
    waktu_terima = db.Column(db.DateTime, default=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'no_amplop': self.no_amplop,
            'nama_pengirim': self.nama_pengirim,
            'jenis': self.jenis,
            'keterangan': self.keterangan,
            'waktu_terima': self.waktu_terima.isoformat() if self.waktu_terima else None
        }

class Crew(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nama = db.Column(db.String(100))
    peran = db.Column(db.String(50))
    no_hp = db.Column(db.String(20))
    status = db.Column(db.String(20), default='Active')
    kode_akses = db.Column(db.String(10), unique=True) 

    def to_dict(self):
        return {
            'id': self.id,
            'nama': self.nama,
            'peran': self.peran,
            'no_hp': self.no_hp,
            'status': self.status,
            'login_code': self.kode_akses
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
# HELPER: GENERATE KODE ACAK
# ==========================================
def generate_unique_code():
    while True:
        chars = string.ascii_uppercase + string.digits
        code = ''.join(random.choices(chars, k=6))
        if not Crew.query.filter_by(kode_akses=code).first():
            return code

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
    config = DesignConfig.query.first() or DesignConfig()
    if not config.id: db.session.add(config); db.session.commit()
    assets_cover = AssetCover.query.order_by(AssetCover.id.desc()).all()
    assets_twibbon = AssetTwibbon.query.order_by(AssetTwibbon.id.desc()).all()
    return render_template('design.html', active_page='design', config=config, assets_cover=assets_cover, assets_twibbon=assets_twibbon)

@app.route('/img_render/<tipe>/<int:id>')
def tampilkan_gambar(tipe, id):
    model = AssetCover if tipe == 'cover' else AssetTwibbon if tipe == 'twibbon' else None
    if not model: return "Tipe salah", 400
    asset = model.query.get_or_404(id)
    if not asset.data_gambar: return "Gambar Kosong", 404
    return send_file(io.BytesIO(asset.data_gambar), mimetype=asset.mimetype, download_name=asset.judul)

@app.route('/api/add_asset', methods=['POST'])
def add_asset():
    if 'file' not in request.files: return jsonify({'status': 'error', 'message': 'No file'}), 400
    file = request.files['file']
    if file.filename == '': return jsonify({'status': 'error', 'message': 'Empty filename'}), 400
    try:
        model = AssetCover if request.form.get('tipe') == 'cover' else AssetTwibbon
        new_asset = model(judul=secure_filename(file.filename), data_gambar=file.read(), mimetype=file.mimetype)
        db.session.add(new_asset)
        db.session.commit()
        return jsonify({'status': 'success', 'img_url': url_for('tampilkan_gambar', tipe=request.form.get('tipe'), id=new_asset.id)})
    except Exception as e: return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/save_design_config', methods=['POST'])
def save_design_config():
    data = request.json
    config = DesignConfig.query.first() or DesignConfig()
    config.judul_mempelai = data.get('judul_mempelai')
    config.tanggal_acara = data.get('tanggal_acara')
    config.tema_warna = data.get('tema_warna')
    if not config.id: db.session.add(config)
    db.session.commit()
    return jsonify({'status': 'success'})

@app.route('/api/delete_asset/<tipe>/<int:id>', methods=['POST'])
def delete_asset(tipe, id):
    try:
        model = AssetCover if tipe == 'cover' else AssetTwibbon
        db.session.delete(model.query.get_or_404(id))
        db.session.commit()
        return jsonify({'status': 'success'})
    except: return jsonify({'status': 'error'}), 500

@app.route('/tamu')
def tamu(): return render_template('tamu.html', active_page='tamu', tamu=Tamu.query.order_by(Tamu.id.desc()).all())

@app.route('/tambah_tamu', methods=['POST'])
def tambah_tamu():
    db.session.add(Tamu(nama=request.form['nama'], kategori=request.form['kategori'], no_hp=request.form['no_hp'], meja=request.form['meja']))
    db.session.commit()
    return redirect(url_for('tamu'))

@app.route('/edit_tamu/<int:id>', methods=['POST'])
def edit_tamu(id):
    t = Tamu.query.get_or_404(id)
    t.nama, t.kategori, t.meja, t.no_hp = request.form['nama'], request.form['kategori'], request.form['meja'], request.form['no_hp']
    db.session.commit()
    return redirect(url_for('tamu'))

@app.route('/hapus_tamu/<int:id>')
def hapus_tamu(id):
    db.session.delete(Tamu.query.get_or_404(id))
    db.session.commit()
    return redirect(url_for('tamu'))

@app.route('/rundown')
def rundown(): return render_template('rundown.html', active_page='rundown', items=Rundown.query.order_by(Rundown.waktu).all())

@app.route('/gifts', methods=['GET', 'POST'])
def gifts():
    if request.method == 'POST':
        db.session.add(Hadiah(no_amplop=request.form.get('no_amplop'), nama_pengirim=request.form.get('nama_pengirim'), jenis=request.form.get('jenis', 'Amplop')))
        db.session.commit()
        return redirect(url_for('gifts'))
    return render_template('gifts.html', active_page='gifts', hadiah=Hadiah.query.order_by(Hadiah.id.desc()).all(), total=Hadiah.query.count())

@app.route('/crew', methods=['GET', 'POST'])
def crew():
    if request.method == 'POST':
        # Generate kode acak saat tambah via web
        db.session.add(Crew(nama=request.form['nama'], peran=request.form['peran'], no_hp=request.form['no_hp'], kode_akses=generate_unique_code()))
        db.session.commit()
        return redirect(url_for('crew'))
    return render_template('crew.html', active_page='crew', crew=Crew.query.all())

@app.route('/edit_crew/<int:id>', methods=['POST'])
def edit_crew(id):
    c = Crew.query.get_or_404(id)
    c.nama, c.peran, c.no_hp, c.status = request.form['nama'], request.form['peran'], request.form['no_hp'], request.form['status']
    db.session.commit()
    return redirect(url_for('crew'))

@app.route('/hapus_crew/<int:id>')
def hapus_crew(id):
    db.session.delete(Crew.query.get_or_404(id))
    db.session.commit()
    return redirect(url_for('crew'))

@app.route('/settings')
def settings(): return render_template('settings.html', active_page='settings')

@app.route('/maps')
def maps(): return render_template('maps.html', active_page='maps', lokasi=Lokasi.query.all())

@app.route('/tambah_lokasi', methods=['POST'])
def tambah_lokasi():
    db.session.add(Lokasi(nama_tempat=request.form['nama_tempat'], alamat=request.form['alamat'], link_gmaps=request.form['link_gmaps'], kategori=request.form['kategori']))
    db.session.commit()
    return redirect(url_for('maps'))

@app.route('/makanan')
def makanan(): return render_template('makanan.html', active_page='makanan', makanan=MenuMakanan.query.all())

@app.route('/tambah_makanan', methods=['POST'])
def tambah_makanan():
    db.session.add(MenuMakanan(nama_menu=request.form['nama_menu'], jenis=request.form['jenis'], deskripsi=request.form['deskripsi'], porsi=request.form['porsi']))
    db.session.commit()
    return redirect(url_for('makanan'))

@app.route('/crew_active_all')
def crew_active_all():
    db.session.execute(text("UPDATE crew SET status='Active'")); db.session.commit()
    return redirect(url_for('crew'))

@app.route('/crew_offline_all')
def crew_offline_all():
    db.session.execute(text("UPDATE crew SET status='Offline'")); db.session.commit()
    return redirect(url_for('crew'))

@app.route('/tambah_rundown', methods=['POST'])
def tambah_rundown():
    db.session.add(Rundown(waktu=request.form['waktu'], judul=request.form['judul'], deskripsi=request.form['deskripsi'], pic=request.form['pic'], status=request.form['status']))
    db.session.commit()
    return redirect(url_for('rundown'))

@app.route('/edit_rundown/<int:id>', methods=['POST'])
def edit_rundown(id):
    item = Rundown.query.get_or_404(id)
    item.waktu, item.judul, item.deskripsi, item.pic, item.status = request.form['waktu'], request.form['judul'], request.form['deskripsi'], request.form['pic'], request.form['status']
    db.session.commit()
    return redirect(url_for('rundown'))

@app.route('/hapus_rundown/<int:id>')
def hapus_rundown(id):
    db.session.delete(Rundown.query.get_or_404(id))
    db.session.commit()
    return redirect(url_for('rundown'))

@app.route('/scan')
def scan_page(): return render_template('scan.html', active_page='scan')

@app.route('/invitation/<slug>')
def view_invitation(slug):
    config = DesignConfig.query.first() or DesignConfig()
    return render_template('invitation.html', config=config)

# ==============================================================================
# 🚀 API MOBILE SERVICES (ENDPOINTS PENTING UNTUK FLUTTER)
# ==============================================================================

# 1. API RUNDOWN (GET)
@app.route('/api/mobile/rundown', methods=['GET'])
def api_get_rundown():
    items = Rundown.query.order_by(Rundown.waktu).all()
    return jsonify({
        'status': 'success',
        'total': len(items),
        'data': [i.to_dict() for i in items]
    })

# 2. API DASHBOARD (GET)
@app.route('/api/mobile/dashboard', methods=['GET'])
def api_get_dashboard():
    total_tamu = Tamu.query.count()
    hadir = Tamu.query.filter_by(status_rsvp='Hadir').count()
    total_hadiah = Hadiah.query.count()
    return jsonify({
        'status': 'success',
        'data': {
            'total_tamu': total_tamu,
            'hadir': hadir,
            'total_hadiah': total_hadiah
        }
    })

# 3. API TAMU (GET & POST)
@app.route('/api/mobile/tamu', methods=['GET', 'POST'])
def api_tamu():
    if request.method == 'GET':
        query = request.args.get('search')
        if query:
            tamu_list = Tamu.query.filter(Tamu.nama.ilike(f"%{query}%")).all()
        else:
            tamu_list = Tamu.query.all()
        return jsonify({'status': 'success', 'data': [t.to_dict() for t in tamu_list]})
    
    # POST
    data = request.get_json()
    new_tamu = Tamu(nama=data.get('nama'), no_hp=data.get('no_hp'), kategori=data.get('kategori', 'Reguler'), meja=data.get('meja', '-'))
    db.session.add(new_tamu)
    db.session.commit()
    return jsonify({'status': 'success', 'message': 'Tamu berhasil ditambahkan', 'data': new_tamu.to_dict()})

# 4. API GIFTS (GET & POST)
@app.route('/api/mobile/gifts', methods=['GET', 'POST'])
def api_gifts():
    if request.method == 'GET':
        gifts = Hadiah.query.order_by(Hadiah.id.desc()).all()
        return jsonify({'status': 'success', 'data': [g.to_dict() for g in gifts]})
    
    # POST
    data = request.get_json()
    new_gift = Hadiah(
        no_amplop=data.get('no_amplop'),
        nama_pengirim=data.get('nama_pengirim'),
        jenis=data.get('jenis', 'Amplop'),
        keterangan=data.get('keterangan', '')
    )
    db.session.add(new_gift)
    db.session.commit()
    return jsonify({'status': 'success', 'message': 'Hadiah disimpan'})

# 5. API SCAN QR (POST)
@app.route('/api/mobile/scan', methods=['POST'])
def api_scan():
    data = request.get_json()
    qr_content = data.get('qr_content')
    return jsonify({'status': 'success', 'message': f'Scan {qr_content} diterima'})

# 6. LOGIN CREW (MENGGUNAKAN KODE ACAK DATABASE)
@app.route('/api/mobile/crew/login', methods=['POST'])
def api_crew_login():
    data = request.get_json()
    kode_akses = data.get('kode_akses')
    if not kode_akses: return jsonify({'status': 'error', 'message': 'Kode akses harus diisi'}), 400
    
    user = Crew.query.filter_by(kode_akses=kode_akses).first()
    if user:
        if user.status != 'Active': return jsonify({'status': 'error', 'message': 'Akun dinonaktifkan.'}), 403
        return jsonify({'status': 'success', 'message': 'Login berhasil', 'data': user.to_dict()})
    return jsonify({'status': 'error', 'message': 'Kode akses tidak valid'}), 401

# 7. LOGIN PHONE (SMART LOGIC)
@app.route('/login-phone', methods=['POST'])
@app.route('/api/mobile/login-phone', methods=['POST'])
def api_login_phone():
    data = request.get_json(silent=True) or request.form
    phone = data.get('phone_number', '').strip()
    if not phone: return jsonify({'status': 'error', 'message': 'Nomor HP wajib'}), 400
    
    # Cek format 08xx dan 62xx
    possible = [phone]
    if phone.startswith('0'): possible.append('62' + phone[1:])
    elif phone.startswith('62'): possible.append('0' + phone[2:])
    
    user = Crew.query.filter(Crew.no_hp.in_(possible)).first()
    if user:
        if user.status != 'Active': return jsonify({'status': 'error', 'message': 'Akun dinonaktifkan'}), 403
        return jsonify({'status': 'success', 'message': 'Login Berhasil', 'data': user.to_dict()})
    
    return jsonify({'status': 'not_found', 'message': 'Nomor HP tidak ditemukan'}), 200

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)