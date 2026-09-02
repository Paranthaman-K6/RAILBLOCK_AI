from .base import BaseAdapter

class TMSAdapter(BaseAdapter):
    source_name = "TMS"
    expected_columns = ["task_id","corridor_id","section_id","line_id","asset_id","task_type","description","severity","estimated_duration_minutes","requires_traffic_block","earliest_start","deadline","department"]

class SMMSAdapter(BaseAdapter):
    source_name = "SMMS"
    expected_columns = ["task_id","corridor_id","section_id","line_id","asset_id","task_type","description","severity","estimated_duration_minutes","requires_signal_disconnection","earliest_start","deadline"]

class TDMSAdapter(BaseAdapter):
    source_name = "TDMS"
    expected_columns = ["task_id","corridor_id","section_id","line_id","asset_id","task_type","description","severity","estimated_duration_minutes","requires_power_isolation","earliest_start","deadline"]

class COAAdapter(BaseAdapter):
    source_name = "COA"
    expected_columns = ["corridor_id","section_id","line_id","asset_id","corridor_name","section_name","line_type"]

class TimetableAdapter(BaseAdapter):
    source_name = "TIMETABLE"
    expected_columns = ["train_id","corridor_id","section_id","line_id","train_type","service_date","departure_time","arrival_time"]

class GoodsForecastAdapter(BaseAdapter):
    source_name = "GOODS_FORECAST"
    expected_columns = ["corridor_id","section_id","line_id","service_date","start_time","end_time","confidence","forecast_count"]

class ResourceAdapter(BaseAdapter):
    source_name = "RESOURCES"
    expected_columns = ["resource_id","resource_type","name","department","capacity","service_date","start_time","end_time"]
