from flask import Flask, render_template, request, redirect, url_for, jsonify
import sqlite3, re
from difflib import SequenceMatcher
from datetime import datetime

app = Flask(__name__)
DB = "ewaste.db"

CATEGORIES = ["Mobile Phone","Laptop","Tablet","Desktop/PC","Monitor","Keyboard","Mouse",
"Printer","Charger/Adapter","Cable","Headphones/Earphones","Battery",
"Arduino/IoT Component","Other Electronics"]

def db():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c

def init_db():
    c=db()
    c.execute("""CREATE TABLE IF NOT EXISTS items(
    id INTEGER PRIMARY KEY AUTOINCREMENT, student_name TEXT NOT NULL, email TEXT NOT NULL,
    item_name TEXT NOT NULL, category TEXT NOT NULL, brand TEXT, condition TEXT NOT NULL,
    age_years REAL, problem TEXT, description TEXT, action TEXT NOT NULL, created_at TEXT NOT NULL)""")
    c.commit(); c.close()

def tokens(s): return set(re.findall(r"[a-z0-9]+",(s or "").lower()))

def similarity(a,b):
    a=(a or "").lower(); b=(b or "").lower()
    A,B=tokens(a),tokens(b)
    jac=len(A&B)/len(A|B) if A|B else 0
    return .6*jac+.4*SequenceMatcher(None,a,b).ratio()

def recommend(category,condition,problem,description):
    c=(category or "").lower(); cond=(condition or "").lower()
    text=((problem or "")+" "+(description or "")).lower()
    if "battery" in c: return "Recycle Safely"
    if cond=="working": return "Reuse / Donate"
    if cond=="partially working": return "Repair / Reuse"
    if cond=="not working":
        if any(w in text for w in ["battery","screen","keyboard","charging","charger","port","software","fan","display","connector","minor"]):
            return "Repair Assessment"
        return "Recycle Responsibly"
    if cond=="damaged": return "Repair Assessment / Recycle"
    return "Assess for Reuse or Recycling"

def impact(action):
    if "Reuse" in action or "Donate" in action:
        return "Keeping a working device in use can extend its useful life and reduce unnecessary replacement."
    if "Repair" in action:
        return "Repair may extend useful life and delay replacement."
    if "Recycle" in action:
        return "Responsible recycling supports safer handling and material recovery."
    return "A condition assessment helps select a responsible next step."

def matches(item):
    c=db()
    rows=c.execute("SELECT * FROM items WHERE id!=? AND action IN ('Reuse / Donate','Repair / Reuse')",(item["id"],)).fetchall()
    c.close(); out=[]
    target=f"{item['item_name']} {item['category']} {item['brand'] or ''} {item['description'] or ''}"
    for r in rows:
        cand=f"{r['item_name']} {r['category']} {r['brand'] or ''} {r['description'] or ''}"
        s=similarity(target,cand)
        if item["category"].lower()==r["category"].lower(): s+=.30
        if item["brand"] and r["brand"] and item["brand"].lower()==r["brand"].lower(): s+=.10
        if s>=.35: out.append({"item":dict(r),"score":round(min(s,1)*100,1)})
    return sorted(out,key=lambda x:x["score"],reverse=True)[:8]

@app.route("/")
def home():
    c=db(); items=c.execute("SELECT * FROM items ORDER BY id DESC").fetchall()
    stats={"total":c.execute("SELECT COUNT(*) FROM items").fetchone()[0],
           "reuse":c.execute("SELECT COUNT(*) FROM items WHERE action LIKE '%Reuse%' OR action LIKE '%Donate%'").fetchone()[0],
           "repair":c.execute("SELECT COUNT(*) FROM items WHERE action LIKE '%Repair%'").fetchone()[0],
           "recycle":c.execute("SELECT COUNT(*) FROM items WHERE action LIKE '%Recycle%'").fetchone()[0]}
    c.close(); return render_template("index.html",items=items,stats=stats,categories=CATEGORIES)

@app.route("/analyze",methods=["POST"])
def analyze():
    f=request.form; action=recommend(f["category"],f["condition"],f.get("problem",""),f.get("description",""))
    c=db(); cur=c.execute("""INSERT INTO items(student_name,email,item_name,category,brand,condition,age_years,problem,description,action,created_at)
    VALUES(?,?,?,?,?,?,?,?,?,?,?)""",(f["student_name"],f["email"],f["item_name"],f["category"],f.get("brand",""),f["condition"],
    float(f.get("age_years") or 0),f.get("problem",""),f.get("description",""),action,datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    c.commit(); item=c.execute("SELECT * FROM items WHERE id=?",(cur.lastrowid,)).fetchone(); c.close()
    return render_template("result.html",item=item,matches=matches(item),impact=impact(action))

@app.route("/delete/<int:item_id>",methods=["POST"])
def delete(item_id):
    c=db(); c.execute("DELETE FROM items WHERE id=?",(item_id,)); c.commit(); c.close(); return redirect(url_for("home"))

@app.route("/api/items")
def api_items():
    c=db(); rows=c.execute("SELECT * FROM items ORDER BY id DESC").fetchall(); c.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/analyze",methods=["POST"])
def api_analyze():
    d=request.get_json(force=True)
    a=recommend(d.get("category",""),d.get("condition",""),d.get("problem",""),d.get("description",""))
    return jsonify({"recommended_action":a,"impact":impact(a)})

if __name__=="__main__":
    init_db(); app.run(debug=True)
