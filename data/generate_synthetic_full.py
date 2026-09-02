import csv, os, random, pathlib
from datetime import datetime, timedelta

random.seed(42)
# ensure correct sample dirs regardless of CWD
base = pathlib.Path(__file__).parent
sample_dir = base / "sample"
synthetic_dir = base / "synthetic"
sample_dir.mkdir(exist_ok=True)
synthetic_dir.mkdir(exist_ok=True)
# also ensure legacy paths for compatibility
os.makedirs("sample", exist_ok=True)
os.makedirs("synthetic", exist_ok=True)

# === Corridors / Sections / Lines / Assets ===
corridors = [
    ("COR-1","Delhi-Howrah","Main freight+passenger"),
    ("COR-2","Mumbai-Chennai","Coastal heavy"),
    ("COR-3","Howrah-Chennai","East Coast"),
]
sections = [
    ("SEC-1","COR-1","Ghaziabad - Tundla",0,120),
    ("SEC-2","COR-1","Tundla - Kanpur",120,320),
    ("SEC-3","COR-2","Kalyan - Pune",0,150),
    ("SEC-4","COR-2","Pune - Solapur",150,350),
    ("SEC-5","COR-3","Vijayawada - Chennai",0,400),
    ("SEC-6","COR-3","Kharagpur - Bhubaneswar",400,700),
]
lines = [
    ("LIN-1","SEC-1","COR-1","UP","UP Line Sec-1"),
    ("LIN-2","SEC-1","COR-1","DOWN","DOWN Line Sec-1"),
    ("LIN-3","SEC-2","COR-1","UP","UP Line Sec-2"),
    ("LIN-4","SEC-2","COR-1","DOWN","DOWN Line Sec-2"),
    ("LIN-5","SEC-3","COR-2","SINGLE","Single Line Sec-3"),
    ("LIN-6","SEC-4","COR-2","LOOP","Loop Line Sec-4"),
    ("LIN-7","SEC-5","COR-3","UP","UP Line Sec-5"),
    ("LIN-8","SEC-6","COR-3","DOWN","DOWN Line Sec-6"),
]
assets = [
    ("AST-1","COR-1","SEC-1","LIN-1","TRACK",92,15.0),
    ("AST-2","COR-1","SEC-1","LIN-2","OHE",88,22.5),
    ("AST-3","COR-1","SEC-2","LIN-3","SIGNAL",85,145.0),
    ("AST-4","COR-1","SEC-2","LIN-4","TRACK",78,180.0),
    ("AST-5","COR-2","SEC-3","LIN-5","TRACK",75,45.0),
    ("AST-6","COR-2","SEC-3","LIN-5","BRIDGE",90,60.0),
    ("AST-7","COR-2","SEC-4","LIN-6","OHE",82,200.0),
    ("AST-8","COR-2","SEC-4","LIN-6","SIGNAL",80,220.0),
    ("AST-9","COR-3","SEC-5","LIN-7","TRACK",70,100.0),
    ("AST-10","COR-3","SEC-5","LIN-7","OHE",77,150.0),
    ("AST-11","COR-3","SEC-6","LIN-8","TRACK",84,500.0),
    ("AST-12","COR-3","SEC-6","LIN-8","SIGNAL",86,550.0),
]

# Write corridors with line/asset mapping (COA)
with open("sample/corridors.csv","w",newline="",encoding="utf-8") as f:
    w=csv.writer(f)
    w.writerow(["corridor_id","corridor_name","section_id","section_name","line_id","line_type","asset_id","asset_type"])
    for (aid,cor,sec,lin,atype,crit,km) in assets:
        sec_name = next(s[2] for s in sections if s[0]==sec)
        lin_type = next(l[3] for l in lines if l[0]==lin)
        cor_name = next(c[1] for c in corridors if c[0]==cor)
        w.writerow([cor,cor_name,sec,sec_name,lin,lin_type,aid,atype])

with open("synthetic/corridors.csv","w",newline="",encoding="utf-8") as f:
    w=csv.writer(f)
    w.writerow(["corridor_id","corridor_name","section_id","section_name","line_id","line_type","asset_id","asset_type"])
    for row in open("sample/corridors.csv").read().strip().split("\n")[1:]:
        f.write(row+"\n")

with open("sample/sections.csv","w",newline="") as f:
    w=csv.writer(f)
    w.writerow(["corridor_id","section_id","section_name","from_km","to_km"])
    for sid,cor,name,fm,to in [(s[0],s[1],s[2],s[3],s[4]) for s in sections]:
        w.writerow([cor,sid,name,fm,to])

with open("sample/lines.csv","w",newline="") as f:
    w=csv.writer(f)
    w.writerow(["corridor_id","section_id","line_id","line_type","name"])
    for lid,sec,cor,ltype,name in lines:
        w.writerow([cor,sec,lid,ltype,name])

with open("sample/assets.csv","w",newline="") as f:
    w=csv.writer(f)
    w.writerow(["corridor_id","section_id","line_id","asset_id","asset_type","asset_criticality","location_km"])
    for aid,cor,sec,lin,atype,crit,km in assets:
        w.writerow([cor,sec,lin,aid,atype,crit,km])

# === Resources ===
resources = [
    ("RES-1","CREW","Track Gang A","ENGINEERING",2),
    ("RES-2","CREW","Track Gang B","ENGINEERING",2),
    ("RES-3","MACHINE","Tamping Machine M1","ENGINEERING",1),
    ("RES-4","MACHINE","Welding Plant W1","ENGINEERING",1),
    ("RES-5","MATERIAL","Ballast Stock","ENGINEERING",10),
    ("RES-6","CREW","Signal Team S1","S_AND_T",2),
    ("RES-7","CREW","Signal Team S2","S_AND_T",2),
    ("RES-8","MACHINE","Signal Test Van","S_AND_T",1),
    ("RES-9","CREW","OHE Crew O1","TRACTION",2),
    ("RES-10","CREW","OHE Crew O2","TRACTION",2),
    ("RES-11","MACHINE","Tower Wagon","TRACTION",1),
    ("RES-12","CREW","Project Team P1","PROJECTS",3),
    ("RES-13","MACHINE","Crane 100T","PROJECTS",1),
    ("RES-14","CREW","Control Office","CONTROL_OFFICE",5),
]

start_date = datetime(2026,9,1)
dates = [(start_date+timedelta(days=i)).strftime("%Y-%m-%d") for i in range(30)] # for monthly

# Write resources with availability for each date
with open("sample/resources.csv","w",newline="") as f:
    w=csv.writer(f)
    w.writerow(["resource_id","resource_type","name","department","capacity","service_date","start_time","end_time"])
    for rid,rtype,name,dept,cap in resources:
        for d in dates[:7]: # weekly availability initially
            w.writerow([rid,rtype,name,dept,cap,d,"00:00","23:59"])
with open("synthetic/resources.csv","w",newline="") as f:
    w=csv.writer(f)
    w.writerow(["resource_id","resource_type","name","department","capacity","service_date","start_time","end_time"])
    for rid,rtype,name,dept,cap in resources:
        for d in dates:
            w.writerow([rid,rtype,name,dept,cap,d,"00:00","23:59"])

with open("sample/resource_availability.csv","w",newline="") as f:
    w=csv.writer(f)
    w.writerow(["resource_id","service_date","start_time","end_time","available"])
    for rid,rtype,name,dept,cap in resources:
        for d in random.sample(dates, 20):
            w.writerow([rid,d,"00:00","23:59","true"])

# === Tasks: 30 across departments, with dependencies, overdue, etc ===
departments = ["ENGINEERING","S_AND_T","TRACTION","PROJECTS"]
task_types = {
    "ENGINEERING": ["TRACK_RENEWAL","BALLAST_CLEANING","TRACK_INSPECTION","BRIDGE_MAINT"],
    "S_AND_T": ["SIGNAL_TEST","POINT_MAINT","CABLE_CHECK","INTERLOCKING"],
    "TRACTION": ["OHE_INSPECTION","OHE_RENEWAL","POWER_ISOLATION","TROLLEY_CHECK"],
    "PROJECTS": ["DOUBLING_WORK","THIRD_LINE","ROB_CONSTRUCTION","YARD_REMODEL"],
}
severities = ["LOW","MEDIUM","HIGH","CRITICAL"]
task_defs = []

# Create 30 tasks
for i in range(1,31):
    tid = f"TSK-{i:03d}"
    dept = departments[(i-1)%len(departments)]
    # assign corridor/section/line/asset round-robin
    asset = assets[(i-1)%len(assets)]
    aid,cor,sec,lin,atype,crit,km = asset
    # override some to ensure grouping possible (some same corridor/section/line)
    if i%5==0:
        cor,sec,lin,aid = "COR-1","SEC-1","LIN-1","AST-1"
    elif i%7==0:
        cor,sec,lin,aid = "COR-1","SEC-1","LIN-2","AST-2"
    ttype = random.choice(task_types[dept])
    sev = random.choice(severities)
    safety = random.randint(30,95)
    urgency = random.randint(20,90)
    acrit = crit
    op_impact = random.randint(30,90)
    overdue = random.choice([0,0,0,2,5,12,20])
    coord = random.randint(30,80)
    readiness = random.randint(50,95)
    est = random.choice([30,45,60,90,120,180])
    setup = random.choice([10,15,20,30])
    block_type = "TRAFFIC"
    requires_traffic = "true"
    # power / signal based on dept
    requires_power = "true" if dept=="TRACTION" and i%2==0 else "false"
    requires_signal = "true" if dept=="S_AND_T" and i%3==0 else "false"
    earliest = (start_date + timedelta(days=random.randint(0,2))).strftime("%Y-%m-%d")
    deadline = (start_date + timedelta(days=random.randint(7,28))).strftime("%Y-%m-%d")
    dep = ""
    if i in [4,8,12,16,20] :
        dep = f"TSK-{i-1:03d}"
    if i==15:
        dep = "TSK-001;TSK-002"
    # resource: pick 1-2 resources from same dept
    dept_res = [r[0] for r in resources if r[3]==dept]
    req_res = ";".join(random.sample(dept_res, k=random.randint(1,2))) if dept_res else ""
    # if engineering task with high coordination, use common resource to test overlap
    if i%6==0:
        req_res = "RES-1"
    task_defs.append([tid,cor,sec,lin,aid,ttype,f"{ttype} at {sec} KM {km} {sev}",sev,safety,urgency,acrit,op_impact,overdue,coord,readiness,est,setup,block_type,requires_traffic,requires_power,requires_signal,earliest,deadline,dep,req_res,dept])

# Post-process dependencies to ensure earliest_start ordering and deadline feasibility
# Build map for quick lookup
task_map = {row[0]: row for row in task_defs}
for row in task_defs:
    tid = row[0]
    dep_str = row[23]
    if dep_str:
        deps = [d.strip() for d in dep_str.split(";") if d.strip()]
        max_earliest = None
        for d in deps:
            if d in task_map:
                dep_earliest = datetime.strptime(task_map[d][21], "%Y-%m-%d")
                if max_earliest is None or dep_earliest > max_earliest:
                    max_earliest = dep_earliest
        if max_earliest:
            new_earliest = max_earliest + timedelta(days=1)
            cur_earliest = datetime.strptime(row[21], "%Y-%m-%d")
            if new_earliest > cur_earliest:
                row[21] = new_earliest.strftime("%Y-%m-%d")
                cur_deadline = datetime.strptime(row[22], "%Y-%m-%d")
                if cur_deadline <= new_earliest:
                    row[22] = (new_earliest + timedelta(days=7)).strftime("%Y-%m-%d")
        continue

with open("sample/tasks.csv","w",newline="",encoding="utf-8") as f:
    w=csv.writer(f)
    w.writerow(["task_id","corridor_id","section_id","line_id","asset_id","task_type","description","severity","safety_score","urgency_score","asset_criticality","operational_impact","overdue_days","coordination_value","resource_readiness","estimated_duration_minutes","setup_duration_minutes","required_block_type","requires_traffic_block","requires_power_isolation","requires_signal_disconnection","earliest_start","deadline","dependency_task_ids","required_resource_ids","department"])
    for row in task_defs:
        w.writerow(row)

with open("synthetic/tasks.csv","w",newline="",encoding="utf-8") as f:
    w=csv.writer(f)
    w.writerow(["task_id","corridor_id","section_id","line_id","asset_id","task_type","description","severity","safety_score","urgency_score","asset_criticality","operational_impact","overdue_days","coordination_value","resource_readiness","estimated_duration_minutes","setup_duration_minutes","required_block_type","requires_traffic_block","requires_power_isolation","requires_signal_disconnection","earliest_start","deadline","dependency_task_ids","required_resource_ids","department"])
    for row in task_defs:
        w.writerow(row)

# === Trains: 14 days, 8 trains per day per corridor ===
with open("sample/trains.csv","w",newline="") as f:
    w=csv.writer(f)
    w.writerow(["train_id","corridor_id","section_id","line_id","train_type","service_date","departure_time","arrival_time","buffer_before","buffer_after"])
    tid=1
    for d in dates[:14]:
        for cor in ["COR-1","COR-2","COR-3"]:
            # passenger morning
            sec = "SEC-1" if cor=="COR-1" else "SEC-3" if cor=="COR-2" else "SEC-5"
            lin = "LIN-1" if cor=="COR-1" else "LIN-5" if cor=="COR-2" else "LIN-7"
            w.writerow([f"TRN-{tid:04d}",cor,sec,lin,"PASSENGER",d,"06:00","06:30",15,15]); tid+=1
            w.writerow([f"TRN-{tid:04d}",cor,sec,lin,"PASSENGER",d,"08:30","09:00",15,15]); tid+=1
            w.writerow([f"TRN-{tid:04d}",cor,sec,lin,"GOODS",d,"10:00","10:45",10,10]); tid+=1
            # avoid candidate windows 01:00-03:00 and 13:30-15:30 intentionally, but add some overlapping to test rejection
            if d in ["2026-09-02","2026-09-05"]:
                w.writerow([f"TRN-{tid:04d}",cor,sec,lin,"PASSENGER",d,"01:30","02:00",15,15]); tid+=1 # overlaps 01:00-03:00 window
            if d=="2026-09-03" and cor=="COR-1":
                w.writerow([f"TRN-{tid:04d}","COR-1","SEC-1","LIN-1","PASSENGER",d,"13:45","14:30",15,15]); tid+=1 # overlaps 13:30-15:30

with open("synthetic/trains.csv","w",newline="") as f:
    f.write(open("sample/trains.csv").read())

# === Goods forecast: varying confidence ===
with open("sample/goods_forecast.csv","w",newline="") as f:
    w=csv.writer(f)
    w.writerow(["corridor_id","section_id","line_id","service_date","start_time","end_time","confidence","forecast_count","risk_score"])
    for d in dates[:14]:
        for cor,sec,lin in [("COR-1","SEC-1","LIN-1"),("COR-2","SEC-3","LIN-5"),("COR-3","SEC-5","LIN-7")]:
            conf = random.choice([0.3,0.4,0.6,0.85])
            w.writerow([cor,sec,lin,d,"02:00","04:00",conf,random.randint(1,4), int(conf*100)])
            if cor=="COR-1" and d=="2026-09-02":
                w.writerow([cor,sec,lin,d,"13:30","15:30",0.9,3,90]) # high confidence to trigger HARD

with open("synthetic/goods_forecast.csv","w",newline="") as f:
    f.write(open("sample/goods_forecast.csv").read())

# Copy other files
for name in ["corridors","sections","lines","assets","resources","resource_availability","trains","goods_forecast","tasks"]:
    pass

print(f"Generated comprehensive synthetic data: {len(task_defs)} tasks, {len(resources)} resources, {len(dates)} days, assets {len(assets)}")
for p in ["sample/tasks.csv","sample/trains.csv","sample/goods_forecast.csv","sample/resources.csv"]:
    print(p, open(p).read().count("\n")-1, "records")
