import os, secrets, hashlib, hmac, csv, io, statistics
from datetime import datetime, date, timedelta
from typing import Optional
from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, ForeignKey, Text, func
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship
from itsdangerous import URLSafeSerializer, BadSignature

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./pharmaamr_demo.db")
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()
signer = URLSafeSerializer(os.getenv("SECRET_KEY", "dev-only-change-me"), salt="pharmaamr-session")
app = FastAPI(title="PharmaAMR-Track", version="0.1.0")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

class Pharmacy(Base):
    __tablename__ = "pharmacies"
    id = Column(Integer, primary_key=True)
    code = Column(String(30), unique=True, nullable=False)
    name = Column(String(160), nullable=False)
    district = Column(String(100), nullable=False)
    state = Column(String(100), default="Madhya Pradesh")
    created_at = Column(DateTime, default=datetime.utcnow)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    role = Column(String(20), default="pharmacy")  # admin or pharmacy
    pharmacy_id = Column(Integer, ForeignKey("pharmacies.id"), nullable=True)
    active = Column(Boolean, default=True)
    pharmacy = relationship("Pharmacy")

class Visit(Base):
    __tablename__ = "visits"
    id = Column(Integer, primary_key=True)
    visit_code = Column(String(40), unique=True, nullable=False)
    patient_token = Column(String(80), nullable=False)
    age_group = Column(String(30), nullable=False)
    sex = Column(String(30), default="Not stated")
    locality = Column(String(100), default="")
    symptoms = Column(Text, default="")
    symptom_duration = Column(String(40), default="Unknown")
    reason_for_visit = Column(String(80), default="New symptoms")
    doctor_consulted = Column(String(20), default="Unknown")
    test_performed = Column(String(20), default="Unknown")
    test_type = Column(String(80), default="")
    prescription_presented = Column(String(20), default="Unknown")
    prescriber_type = Column(String(80), default="Unknown")
    request_source = Column(String(80), default="Unknown")
    reason_for_request = Column(String(100), default="Unknown")
    previous_antibiotic_90d = Column(String(20), default="Unknown")
    previous_course_completed = Column(String(30), default="Unknown")
    dispensing_outcome = Column(String(40), default="Dispensed")
    referral = Column(String(20), default="No")
    counselling = Column(Boolean, default=False)
    notes = Column(Text, default="")
    pharmacy_id = Column(Integer, ForeignKey("pharmacies.id"), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    medicines = relationship("MedicineRecord", cascade="all, delete-orphan")

class MedicineRecord(Base):
    __tablename__ = "medicine_records"
    id = Column(Integer, primary_key=True)
    visit_id = Column(Integer, ForeignKey("visits.id"), nullable=False)
    generic_name = Column(String(160), nullable=False)
    brand_name = Column(String(160), default="")
    strength = Column(String(80), default="")
    dosage_form = Column(String(60), default="")
    route = Column(String(40), default="Oral")
    quantity_dispensed = Column(String(60), default="0")
    prescribed_duration_days = Column(Integer, nullable=True)
    aware_category = Column(String(20), default="Unclassified")
    atc_code = Column(String(30), default="")
    requested = Column(Boolean, default=True)
    dispensed = Column(Boolean, default=True)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String(100), nullable=False)
    record_type = Column(String(50), default="")
    record_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 240000).hex()
    return f"{salt}${digest}"

def verify_password(password: str, stored: str) -> bool:
    try:
        salt, digest = stored.split("$", 1)
        test = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 240000).hex()
        return hmac.compare_digest(test, digest)
    except Exception:
        return False

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def seed_demo():
    db = SessionLocal()
    try:
        if db.query(User).count():
            return
        p1 = Pharmacy(code="BPL-001", name="Demo Pharmacy - Bhopal Central", district="Bhopal")
        p2 = Pharmacy(code="BPL-002", name="Demo Pharmacy - Raisen Road", district="Bhopal")
        p3 = Pharmacy(code="IND-001", name="Demo Pharmacy - Indore", district="Indore")
        db.add_all([p1, p2, p3]); db.flush()
        db.add_all([
            User(username="admin", password_hash=hash_password("Admin@12345"), role="admin"),
            User(username="pharmacy1", password_hash=hash_password("Pharmacy@123"), role="pharmacy", pharmacy_id=p1.id),
            User(username="pharmacy2", password_hash=hash_password("Pharmacy@123"), role="pharmacy", pharmacy_id=p2.id),
            User(username="pharmacy3", password_hash=hash_password("Pharmacy@123"), role="pharmacy", pharmacy_id=p3.id),
        ])
        db.commit()
    finally:
        db.close()

if os.getenv("SEED_DEMO", "true").lower() == "true":
    seed_demo()

def current_user(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("pharmaamr_session")
    if not token:
        return None
    try:
        data = signer.loads(token)
        user = db.query(User).filter(User.id == data.get("uid"), User.active == True).first()
        return user
    except BadSignature:
        return None

def require_user(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Please sign in")
    return user

def render(request, template, context=None, status_code=200):
    ctx = {"request": request, "user": None}
    if context: ctx.update(context)
    return templates.TemplateResponse(template, ctx, status_code=status_code)

@app.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    return RedirectResponse("/dashboard", status_code=303)

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return render(request, "login.html", {"error": None})

@app.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username.strip(), User.active == True).first()
    if not user or not verify_password(password, user.password_hash):
        return render(request, "login.html", {"error": "Incorrect username or password."}, 401)
    response = RedirectResponse("/dashboard", status_code=303)
    response.set_cookie("pharmaamr_session", signer.dumps({"uid": user.id}), httponly=True, samesite="lax", secure=os.getenv("COOKIE_SECURE", "false").lower()=="true", max_age=60*60*12)
    return response

@app.get("/logout")
def logout():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("pharmaamr_session")
    return response

def visible_visits(db: Session, user: User):
    q = db.query(Visit)
    if user.role != "admin":
        q = q.filter(Visit.pharmacy_id == user.pharmacy_id)
    return q

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)):
    visits_q = visible_visits(db, user)
    total_visits = visits_q.count()
    antibiotic_tx = db.query(MedicineRecord).join(Visit).filter(
        *([] if user.role == "admin" else [Visit.pharmacy_id == user.pharmacy_id])
    ).filter(MedicineRecord.dispensed == True).count()
    no_rx = visits_q.filter(Visit.prescription_presented == "No").count()
    pharmacies = db.query(Pharmacy).count() if user.role == "admin" else 1
    aware_rows = db.query(MedicineRecord.aware_category, func.count(MedicineRecord.id)).join(Visit)
    if user.role != "admin": aware_rows = aware_rows.filter(Visit.pharmacy_id == user.pharmacy_id)
    aware = dict(aware_rows.group_by(MedicineRecord.aware_category).all())
    recent = visits_q.order_by(Visit.created_at.desc()).limit(8).all()
    top_rows = db.query(MedicineRecord.generic_name, func.count(MedicineRecord.id)).join(Visit)
    if user.role != "admin": top_rows = top_rows.filter(Visit.pharmacy_id == user.pharmacy_id)
    top = top_rows.filter(MedicineRecord.dispensed == True).group_by(MedicineRecord.generic_name).order_by(func.count(MedicineRecord.id).desc()).limit(5).all()
    context = dict(user=user, total_visits=total_visits, antibiotic_tx=antibiotic_tx, no_rx=no_rx,
                   pharmacies=pharmacies, aware=aware, recent=recent, top=top)
    return render(request, "dashboard.html", context)

@app.get("/visits/new", response_class=HTMLResponse)
def new_visit_page(request: Request, user: User = Depends(require_user)):
    return render(request, "new_visit.html", {"user": user, "error": None})

@app.post("/visits/new")
def create_visit(
    request: Request,
    age_group: str = Form(...), sex: str = Form("Not stated"), locality: str = Form(""),
    symptoms: str = Form(""), symptom_duration: str = Form("Unknown"),
    reason_for_visit: str = Form("New symptoms"), doctor_consulted: str = Form("Unknown"),
    test_performed: str = Form("Unknown"), test_type: str = Form(""),
    prescription_presented: str = Form("Unknown"), prescriber_type: str = Form("Unknown"),
    request_source: str = Form("Unknown"), reason_for_request: str = Form("Unknown"),
    previous_antibiotic_90d: str = Form("Unknown"), previous_course_completed: str = Form("Unknown"),
    dispensing_outcome: str = Form("Dispensed"), referral: str = Form("No"),
    counselling: Optional[str] = Form(None), generic_name: str = Form(""),
    brand_name: str = Form(""), strength: str = Form(""), dosage_form: str = Form("Tablet"),
    route: str = Form("Oral"), quantity_dispensed: str = Form("0"),
    prescribed_duration_days: str = Form(""), aware_category: str = Form("Unclassified"),
    atc_code: str = Form(""), requested: Optional[str] = Form(None), dispensed: Optional[str] = Form(None),
    user: User = Depends(require_user), db: Session = Depends(get_db)
):
    if user.role != "admin" and not user.pharmacy_id:
        raise HTTPException(403, "Pharmacy account is not assigned to a pharmacy.")
    if not generic_name.strip():
        return render(request, "new_visit.html", {"user": user, "error": "Enter the antibiotic generic name, or use 'Not recorded' if no antibiotic was requested."}, 400)
    visit = Visit(
        visit_code="VIS-" + secrets.token_hex(5).upper(),
        patient_token="PT-" + secrets.token_hex(5).upper(),
        age_group=age_group, sex=sex, locality=locality.strip(), symptoms=symptoms,
        symptom_duration=symptom_duration, reason_for_visit=reason_for_visit,
        doctor_consulted=doctor_consulted, test_performed=test_performed, test_type=test_type,
        prescription_presented=prescription_presented, prescriber_type=prescriber_type,
        request_source=request_source, reason_for_request=reason_for_request,
        previous_antibiotic_90d=previous_antibiotic_90d, previous_course_completed=previous_course_completed,
        dispensing_outcome=dispensing_outcome, referral=referral, counselling=bool(counselling),
        pharmacy_id=user.pharmacy_id, created_by=user.id
    )
    try:
        duration = int(prescribed_duration_days) if prescribed_duration_days.strip() else None
    except ValueError:
        duration = None
    med = MedicineRecord(
        generic_name=generic_name.strip(), brand_name=brand_name.strip(), strength=strength.strip(),
        dosage_form=dosage_form, route=route, quantity_dispensed=quantity_dispensed,
        prescribed_duration_days=duration, aware_category=aware_category, atc_code=atc_code.strip(),
        requested=bool(requested), dispensed=bool(dispensed)
    )
    visit.medicines.append(med)
    db.add(visit); db.flush()
    db.add(AuditLog(user_id=user.id, action="CREATE_VISIT", record_type="visit", record_id=visit.id))
    db.commit()
    return RedirectResponse(f"/visits/{visit.id}", status_code=303)

@app.get("/visits/{visit_id}", response_class=HTMLResponse)
def visit_detail(visit_id: int, request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)):
    q = db.query(Visit).filter(Visit.id == visit_id)
    if user.role != "admin": q = q.filter(Visit.pharmacy_id == user.pharmacy_id)
    visit = q.first()
    if not visit: raise HTTPException(404, "Record not found")
    pharmacy = db.query(Pharmacy).filter(Pharmacy.id == visit.pharmacy_id).first()
    return render(request, "visit_detail.html", {"user": user, "visit": visit, "pharmacy": pharmacy})

@app.get("/export.csv")
def export_csv(user: User = Depends(require_user), db: Session = Depends(get_db)):
    visits = visible_visits(db, user).order_by(Visit.created_at.desc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["visit_code","patient_token","created_at","pharmacy_id","age_group","sex","locality","symptoms",
                     "prescription_presented","prescriber_type","request_source","reason_for_request","previous_antibiotic_90d",
                     "dispensing_outcome","referral","generic_name","brand_name","strength","dosage_form","route",
                     "quantity_dispensed","duration_days","aware_category","atc_code","dispensed"])
    for v in visits:
        for m in v.medicines:
            writer.writerow([v.visit_code,v.patient_token,v.created_at.isoformat(),v.pharmacy_id,v.age_group,v.sex,v.locality,
                v.symptoms,v.prescription_presented,v.prescriber_type,v.request_source,v.reason_for_request,
                v.previous_antibiotic_90d,v.dispensing_outcome,v.referral,m.generic_name,m.brand_name,m.strength,
                m.dosage_form,m.route,m.quantity_dispensed,m.prescribed_duration_days,m.aware_category,m.atc_code,m.dispensed])
    output.seek(0)
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition":"attachment; filename=pharmaamr_records.csv"})

@app.get("/alerts", response_class=HTMLResponse)
def alerts(request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)):
    q = db.query(MedicineRecord, Visit).join(Visit)
    if user.role != "admin": q = q.filter(Visit.pharmacy_id == user.pharmacy_id)
    rows = q.all()
    # Simple transparent baseline: compare recent 7-day count with preceding 7-day count.
    now = datetime.utcnow()
    recent_start, prior_start = now - timedelta(days=7), now - timedelta(days=14)
    recent_count = sum(1 for m,v in rows if v.created_at and v.created_at >= recent_start and m.dispensed)
    prior_count = sum(1 for m,v in rows if v.created_at and prior_start <= v.created_at < recent_start and m.dispensed)
    flags = []
    if recent_count >= 5 and prior_count > 0 and recent_count >= prior_count * 1.5:
        flags.append(f"Dispensing activity increased from {prior_count} to {recent_count} records versus the previous 7-day period. Review the data; this is not proof of an outbreak or inappropriate use.")
    if recent_count >= 10 and prior_count == 0:
        flags.append("Recent dispensing records are present but no prior-week baseline exists. Continue collecting data before interpreting a trend.")
    if not flags:
        flags.append("No unusual dispensing trend detected by the simple demo rule. Low data volume can limit detection.")
    missing = sum(1 for m,v in rows if not v.symptoms or v.prescription_presented == "Unknown" or m.aware_category == "Unclassified")
    return render(request, "alerts.html", {"user": user, "flags": flags, "recent_count": recent_count,
                   "prior_count": prior_count, "missing": missing, "total": len(rows)})

@app.get("/pharmacies", response_class=HTMLResponse)
def pharmacies_page(request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)):
    if user.role != "admin": raise HTTPException(403, "Administrator access required")
    pharmacies = db.query(Pharmacy).order_by(Pharmacy.district, Pharmacy.name).all()
    counts = {p.id: db.query(Visit).filter(Visit.pharmacy_id == p.id).count() for p in pharmacies}
    return render(request, "pharmacies.html", {"user": user, "pharmacies": pharmacies, "counts": counts})

@app.get("/health")
def health():
    return {"status":"ok","service":"PharmaAMR-Track","database":"connected"}
