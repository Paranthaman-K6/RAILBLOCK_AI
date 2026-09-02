import csv, os

os.makedirs("sample", exist_ok=True)

# corridors
with open("sample/corridors.csv","w",newline="") as f:
    w=csv.writer(f)
    w.writerow(["corridor_id","corridor_name","section_id","section_name","line_id","line_type","asset_id","asset_type"])
    w.writerow(["COR-1","Delhi-Howrah","SEC-1","Ghaziabad-Tundla","LIN-1","UP","AST-1","TRACK"])
    w.writerow(["COR-1","Delhi-Howrah","SEC-1","Ghaziabad-Tundla","LIN-2","DOWN","AST-2","OHE"])
    w.writerow(["COR-1","Delhi-Howrah","SEC-2","Tundla-Kanpur","LIN-3","UP","AST-3","SIGNAL"])
    w.writerow(["COR-2","Mumbai-Chennai","SEC-3","Kalyan-Pune","LIN-4","SINGLE","AST-4","TRACK"])

with open("sample/sections.csv","w",newline="") as f:
    w=csv.writer(f)
    w.writerow(["corridor_id","section_id","section_name","from_km","to_km"])
    w.writerow(["COR-1","SEC-1","Ghaziabad-Tundla","0","100"])
    w.writerow(["COR-1","SEC-2","Tundla-Kanpur","100","250"])

with open("sample/lines.csv","w",newline="") as f:
    w=csv.writer(f)
    w.writerow(["corridor_id","section_id","line_id","line_type","name"])
    w.writerow(["COR-1","SEC-1","LIN-1","UP","UP Line SEC-1"])
    w.writerow(["COR-1","SEC-1","LIN-2","DOWN","DOWN Line SEC-1"])

with open("sample/assets.csv","w",newline="") as f:
    w=csv.writer(f)
    w.writerow(["corridor_id","section_id","line_id","asset_id","asset_type","asset_criticality","location_km"])
    w.writerow(["COR-1","SEC-1","LIN-1","AST-1","TRACK","90","10"])
    w.writerow(["COR-1","SEC-1","LIN-2","AST-2","OHE","80","20"])

with open("sample/tasks.csv","w",newline="") as f:
    w=csv.writer(f)
    w.writerow(["task_id","corridor_id","section_id","line_id","asset_id","task_type","description","severity","safety_score","urgency_score","asset_criticality","operational_impact","overdue_days","coordination_value","resource_readiness","estimated_duration_minutes","setup_duration_minutes","required_block_type","requires_traffic_block","requires_power_isolation","requires_signal_disconnection","earliest_start","deadline","dependency_task_ids","required_resource_ids","department"])
    w.writerow(["TSK-1","COR-1","SEC-1","LIN-1","AST-1","MAINTENANCE","Track renewal HIGH","HIGH","90","80","85","70","12","60","75","60","15","TRAFFIC","true","false","false","2026-09-01","2026-09-10","","RES-1","ENGINEERING"])
    w.writerow(["TSK-2","COR-1","SEC-1","LIN-1","AST-1","INSPECTION","Inspection LOW","LOW","40","30","50","40","0","30","50","30","10","TRAFFIC","true","false","false","2026-09-01","2026-09-15","","RES-2","ENGINEERING"])
    w.writerow(["TSK-3","COR-1","SEC-1","LIN-2","AST-2","OHE_MAINTENANCE","OHE check","MEDIUM","70","60","80","60","2","70","80","90","15","TRAFFIC","true","true","false","2026-09-01","2026-09-12","","RES-4","TRACTION"])
    w.writerow(["TSK-4","COR-1","SEC-2","LIN-3","AST-3","SIGNAL_TEST","Signal test","HIGH","85","70","90","75","5","50","60","45","10","TRAFFIC","true","false","true","2026-09-01","2026-09-08","TSK-1","RES-3","S_AND_T"])

with open("sample/trains.csv","w",newline="") as f:
    w=csv.writer(f)
    w.writerow(["train_id","corridor_id","section_id","line_id","train_type","service_date","departure_time","arrival_time","buffer_before","buffer_after"])
    w.writerow(["TRN-1","COR-1","SEC-1","LIN-1","PASSENGER","2026-09-02","480","540","15","15"])
    w.writerow(["TRN-2","COR-1","SEC-1","LIN-1","GOODS","2026-09-02","800","860","15","15"])

with open("sample/goods_forecast.csv","w",newline="") as f:
    w=csv.writer(f)
    w.writerow(["corridor_id","section_id","line_id","service_date","start_time","end_time","confidence","forecast_count","risk_score"])
    w.writerow(["COR-1","SEC-1","LIN-1","2026-09-02","600","700","0.8","3","75"])
    w.writerow(["COR-1","SEC-1","LIN-1","2026-09-03","600","700","0.4","2","40"])

with open("sample/resources.csv","w",newline="") as f:
    w=csv.writer(f)
    w.writerow(["resource_id","resource_type","name","department","capacity","service_date","start_time","end_time"])
    w.writerow(["RES-1","CREW","Track Crew A","ENGINEERING","1","2026-09-01","0","1439"])
    w.writerow(["RES-2","MACHINE","Welding Machine","ENGINEERING","1","2026-09-01","0","1439"])
    w.writerow(["RES-3","CREW","Signal Crew B","S_AND_T","1","2026-09-02","0","1439"])
    w.writerow(["RES-4","CREW","OHE Crew C","TRACTION","1","2026-09-02","0","1439"])

with open("sample/resource_availability.csv","w",newline="") as f:
    w=csv.writer(f)
    w.writerow(["resource_id","service_date","start_time","end_time","available"])
    w.writerow(["RES-1","2026-09-02","0","1439","true"])

print("Generated sample data")
