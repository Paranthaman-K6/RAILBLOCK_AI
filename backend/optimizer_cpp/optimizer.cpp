#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <string>
#include <vector>
#include <map>
#include <set>
#include <algorithm>
#include <chrono>
#include <stdexcept>

namespace py = pybind11;

#if defined(HAS_ORTOOLS) && HAS_ORTOOLS
#include "ortools/sat/cp_model.h"
using namespace operations_research::sat;
#endif

// ---------- Helpers: parse JSON via Python's json module (avoids nlohmann dep) ----------
struct TaskInfo {
    std::string id;
    std::string corridor_id;
    std::string section_id;
    std::string line_id;
    double priority_score = 50;
    std::string priority_band = "MEDIUM";
    int duration = 60; // estimated_duration_minutes
    int setup = 15;    // setup_duration_minutes
    bool power = false;
    bool signal = false;
    std::string block_type = "TRAFFIC";
    int overdue_days = 0;
    double asset_criticality = 50;
    std::string department = "ENGINEERING";
    std::vector<std::string> resource_ids;
    std::string earliest_start; // YYYY-MM-DD or ""
    std::string deadline;       // YYYY-MM-DD or ""
    std::vector<std::string> depends_on; // task ids
};

struct WindowInfo {
    std::string id;
    std::string service_date; // YYYY-MM-DD
    std::string corridor_id;
    std::string section_id;
    std::string line_id;
    int start_time = 0; // minutes from midnight
    int end_time = 0;
    int available_minutes = 0;
    std::string block_type = "TRAFFIC";
    bool power = false;
    bool signal = false;
    int expected_train_count = 0;
    double goods_risk_score = 0;
    std::string status = "FEASIBLE";
};

static std::string get_str(py::dict d, const char* key, std::string def = "") {
    if (!d.contains(key)) return def;
    py::object v = d[key];
    if (v.is_none()) return def;
    try {
        if (py::isinstance<py::str>(v)) return v.cast<std::string>();
        // numbers etc -> py::str
        return py::str(v).cast<std::string>();
    } catch (...) { return def; }
}

static int get_int(py::dict d, const char* key, int def = 0) {
    if (!d.contains(key)) return def;
    py::object v = d[key];
    if (v.is_none()) return def;
    try { return v.cast<int>(); } catch (...) {
        try { return (int)v.cast<double>(); } catch (...) {
            try { return std::stoi(py::str(v).cast<std::string>()); } catch (...) { return def; }
        }
    }
}

static double get_double(py::dict d, const char* key, double def = 0) {
    if (!d.contains(key)) return def;
    py::object v = d[key];
    if (v.is_none()) return def;
    try { return v.cast<double>(); } catch (...) {
        try { return (double)v.cast<int>(); } catch (...) { return def; }
    }
}

static bool get_bool(py::dict d, const char* key, bool def = false) {
    if (!d.contains(key)) return def;
    py::object v = d[key];
    if (v.is_none()) return def;
    try { return v.cast<bool>(); } catch (...) {
        std::string s = py::str(v).cast<std::string>();
        std::transform(s.begin(), s.end(), s.begin(), ::tolower);
        return s == "true" || s == "1" || s == "yes";
    }
}

static std::vector<std::string> get_str_list(py::dict d, const char* key) {
    std::vector<std::string> out;
    if (!d.contains(key)) return out;
    py::object v = d[key];
    if (v.is_none()) return out;
    if (py::isinstance<py::list>(v) || py::isinstance<py::tuple>(v)) {
        for (auto item : v.cast<py::list>()) {
            try { out.push_back(py::str(item).cast<std::string>()); } catch (...) {}
        }
    } else if (py::isinstance<py::str>(v)) {
        // comma-separated fallback
        std::string s = v.cast<std::string>();
        if (!s.empty() && s.front() == '[') {
            // try json loads via python
            try {
                py::module json = py::module::import("json");
                py::object lst = json.attr("loads")(s);
                for (auto item : lst.cast<py::list>()) out.push_back(py::str(item).cast<std::string>());
            } catch (...) { out.push_back(s); }
        } else if (!s.empty()) out.push_back(s);
    }
    return out;
}

static TaskInfo parse_task(py::dict d) {
    TaskInfo t;
    t.id = get_str(d, "id", get_str(d, "task_id", ""));
    t.corridor_id = get_str(d, "corridor_id");
    t.section_id = get_str(d, "section_id");
    t.line_id = get_str(d, "line_id");
    t.priority_score = get_double(d, "priority_score", 50);
    if (d.contains("priority_score") && d["priority_score"].is_none()) t.priority_score = 50;
    t.priority_band = get_str(d, "priority_band", "MEDIUM");
    t.duration = get_int(d, "estimated_duration_minutes", get_int(d, "duration", 60));
    t.setup = get_int(d, "setup_duration_minutes", get_int(d, "setup", 15));
    t.power = get_bool(d, "requires_power_isolation", false);
    t.signal = get_bool(d, "requires_signal_disconnection", false);
    t.block_type = get_str(d, "required_block_type", get_str(d, "block_type", "TRAFFIC"));
    t.overdue_days = get_int(d, "overdue_days", 0);
    t.asset_criticality = get_double(d, "asset_criticality", 50);
    t.department = get_str(d, "department", "ENGINEERING");
    t.resource_ids = get_str_list(d, "resource_ids");
    if (t.resource_ids.empty()) t.resource_ids = get_str_list(d, "resources");
    // alternative single resource_id field
    if (t.resource_ids.empty()) {
        std::string rid = get_str(d, "resource_id");
        if (!rid.empty()) t.resource_ids.push_back(rid);
    }
    t.earliest_start = get_str(d, "earliest_start");
    // handle earliest_start as date substring 0:10 if datetime
    if (t.earliest_start.size() > 10) t.earliest_start = t.earliest_start.substr(0, 10);
    t.deadline = get_str(d, "deadline");
    if (t.deadline.size() > 10) t.deadline = t.deadline.substr(0, 10);
    t.depends_on = get_str_list(d, "depends_on");
    if (t.depends_on.empty()) t.depends_on = get_str_list(d, "dependencies");
    if (t.depends_on.empty()) t.depends_on = get_str_list(d, "depends_on_task_ids");
    return t;
}

static WindowInfo parse_window(py::dict d) {
    WindowInfo w;
    w.id = get_str(d, "id", get_str(d, "window_id", ""));
    w.service_date = get_str(d, "service_date");
    if (w.service_date.size() > 10) w.service_date = w.service_date.substr(0, 10);
    w.corridor_id = get_str(d, "corridor_id");
    w.section_id = get_str(d, "section_id");
    w.line_id = get_str(d, "line_id");
    w.start_time = get_int(d, "start_time", 0);
    w.end_time = get_int(d, "end_time", 0);
    w.available_minutes = get_int(d, "available_minutes", w.end_time - w.start_time);
    if (w.available_minutes <= 0 && w.end_time > w.start_time) w.available_minutes = w.end_time - w.start_time;
    w.block_type = get_str(d, "block_type", "TRAFFIC");
    w.power = get_bool(d, "requires_power_isolation", false);
    w.signal = get_bool(d, "requires_signal_disconnection", false);
    w.expected_train_count = get_int(d, "expected_train_count", 0);
    w.goods_risk_score = get_double(d, "goods_risk_score", 0);
    w.status = get_str(d, "status", "FEASIBLE");
    return w;
}

static bool hard_conflict(const TaskInfo& t, const WindowInfo& w) {
    if (!t.corridor_id.empty() && !w.corridor_id.empty() && t.corridor_id != w.corridor_id) return true;
    if (!t.section_id.empty() && !w.section_id.empty() && t.section_id != w.section_id) return true;
    if (!t.line_id.empty() && !w.line_id.empty() && t.line_id != w.line_id) return true;
    if (!t.block_type.empty() && !w.block_type.empty() && t.block_type != w.block_type) return true;
    if (t.power && !w.power) return true;
    if (t.signal && !w.signal) return true;
    if (t.duration + t.setup > w.available_minutes) return true;
    if (w.goods_risk_score >= 70) return true;
    if (w.status == "REJECTED") return true;
    if (!t.earliest_start.empty() && !w.service_date.empty() && w.service_date < t.earliest_start) return true;
    if (!t.deadline.empty() && !w.service_date.empty() && w.service_date > t.deadline) return true;
    if (t.duration + t.setup > 240) return true; // MAX_BLOCK_DURATION
    if (w.available_minutes > 240) return true; // template max 240 guard
    return false;
}

// Compute net benefit for objective (mirrors optimizer.py)
static int compute_net(const TaskInfo& t, const WindowInfo& w) {
    int comp_priority = (int)((t.priority_score) * 10);
    int comp_critical = (t.priority_band == "CRITICAL") ? 200 : 0;
    int comp_overdue = std::min(20, t.overdue_days * 2) * 10;
    int comp_asset = (int)(t.asset_criticality * 0.5);
    int train_pen = (int)((w.goods_risk_score * 0.2 + w.expected_train_count * 5) * 10);
    int unused = std::max(0, w.available_minutes - (t.duration + t.setup));
    int unused_pen = unused * 1;
    return comp_priority + comp_critical + comp_overdue + comp_asset - train_pen - unused_pen;
}

// ---------------- Main solve impl ----------------
std::string solve_impl(const std::string& blocks_json, const std::string& tasks_json, int time_limit) {
    auto t0 = std::chrono::steady_clock::now();
    py::gil_scoped_acquire gil;
    py::module json_mod = py::module::import("json");

    py::object blocks_obj = json_mod.attr("loads")(blocks_json);
    py::object tasks_obj = json_mod.attr("loads")(tasks_json);

    py::list blocks_list = blocks_obj.cast<py::list>();
    py::list tasks_list = tasks_obj.cast<py::list>();

    std::vector<TaskInfo> tasks;
    tasks.reserve(py::len(tasks_list));
    for (auto item : tasks_list) {
        py::dict d = item.cast<py::dict>();
        tasks.push_back(parse_task(d));
    }
    std::vector<WindowInfo> windows;
    windows.reserve(py::len(blocks_list));
    for (auto item : blocks_list) {
        py::dict d = item.cast<py::dict>();
        windows.push_back(parse_window(d));
    }

    if (tasks.empty() || windows.empty()) {
        py::dict res;
        res["status"] = "INFEASIBLE";
        res["reason"] = "No tasks or no windows";
        res["assignments"] = py::list();
        res["objective_value"] = 0;
        res["solver"] = "cpp-cp-sat";
        res["time_limit"] = time_limit;
        res["workers"] = 8;
        return json_mod.attr("dumps")(res).cast<std::string>();
    }

    // Sort tasks by priority desc to improve solver warm start; windows by date/time
    std::sort(tasks.begin(), tasks.end(), [](const TaskInfo& a, const TaskInfo& b){ return a.priority_score > b.priority_score; });
    std::sort(windows.begin(), windows.end(), [](const WindowInfo& a, const WindowInfo& b){
        if (a.service_date != b.service_date) return a.service_date < b.service_date;
        return a.start_time < b.start_time;
    });

    // Build task index map
    std::map<std::string,int> task_idx;
    for (size_t i=0;i<tasks.size();++i) task_idx[tasks[i].id] = (int)i;
    std::map<std::string,int> win_idx;
    for (size_t i=0;i<windows.size();++i) win_idx[windows[i].id] = (int)i;

    // Dependency map: task_id -> list of depends_on ids (filtered to existing tasks)
    std::map<std::string, std::vector<std::string>> dep_map;
    for (auto &t : tasks) {
        for (auto &dep : t.depends_on) if (task_idx.count(dep)) dep_map[t.id].push_back(dep);
    }

#if defined(HAS_ORTOOLS) && HAS_ORTOOLS
    try {
        CpModelBuilder cp_model;

        struct VarInfo { int ti; int wi; BoolVar var; int net; };
        std::vector<VarInfo> vars;
        // map ti -> list idx, wi -> list idx
        std::map<std::pair<int,int>, int> var_index;
        for (size_t ti=0; ti<tasks.size(); ++ti) {
            for (size_t wi=0; wi<windows.size(); ++wi) {
                if (hard_conflict(tasks[ti], windows[wi])) continue;
                int net = compute_net(tasks[ti], windows[wi]);
                std::string name = "x_" + tasks[ti].id + "_" + windows[wi].id;
                BoolVar v = cp_model.NewBoolVar().WithName(name);
                int idx = (int)vars.size();
                vars.push_back({(int)ti,(int)wi,v,net});
                var_index[{(int)ti,(int)wi}] = idx;
            }
        }

        if (vars.empty()) {
            py::dict res;
            res["status"] = "INFEASIBLE";
            res["reason"] = "No feasible task-window pairs after hard checks";
            res["assignments"] = py::list();
            res["objective_value"] = 0;
            res["solver"] = "cpp-cp-sat";
            res["workers"] = 8;
            return json_mod.attr("dumps")(res).cast<std::string>();
        }

        // Objective: Maximize sum(net * var)
        LinearExpr objective;
        for (auto &vi : vars) {
            objective += vi.var * vi.net;
        }
        cp_model.Maximize(objective);

        // Constraint: task at most once
        for (size_t ti=0; ti<tasks.size(); ++ti) {
            LinearExpr sum;
            int cnt=0;
            for (auto &vi : vars) if (vi.ti == (int)ti) { sum += vi.var; cnt++; }
            if (cnt > 1) cp_model.AddLessOrEqual(sum, 1);
            else if (cnt==1) cp_model.AddLessOrEqual(sum, 1);
        }
        // Constraint: window at most once
        for (size_t wi=0; wi<windows.size(); ++wi) {
            LinearExpr sum;
            int cnt=0;
            for (auto &vi : vars) if (vi.wi == (int)wi) { sum += vi.var; cnt++; }
            if (cnt > 1) cp_model.AddLessOrEqual(sum, 1);
        }

        // Resource non-overlap per date
        // Collect resources per task
        std::map<std::string, std::vector<int>> resource_to_task_indices; // not needed; we use per date vars
        // Build map: date -> resource -> vars
        std::map<std::string, std::map<std::string, std::vector<BoolVar>>> date_res_vars;
        for (auto &vi : vars) {
            const auto &t = tasks[vi.ti];
            const auto &w = windows[vi.wi];
            for (auto &rid : t.resource_ids) {
                date_res_vars[w.service_date][rid].push_back(vi.var);
            }
        }
        for (auto &date_pair : date_res_vars) {
            for (auto &res_pair : date_pair.second) {
                auto &vec = res_pair.second;
                if (vec.size() > 1) {
                    LinearExpr sum;
                    for (auto &v : vec) sum += v;
                    cp_model.AddLessOrEqual(sum, 1);
                }
            }
        }

        // Dependency constraints: task <= depends_on sum, and temporal
        for (auto &kv : dep_map) {
            std::string task_id = kv.first;
            int ti = task_idx[task_id];
            // collect task vars
            std::vector<BoolVar> task_vars;
            std::vector<VarInfo*> task_var_infos;
            for (auto &vi : vars) if (vi.ti == ti) { task_vars.push_back(vi.var); task_var_infos.push_back(&vi); }
            if (task_vars.empty()) continue;
            for (auto &dep_id : kv.second) {
                int dep_ti = task_idx[dep_id];
                std::vector<BoolVar> dep_vars;
                std::vector<VarInfo*> dep_var_infos;
                for (auto &vi : vars) if (vi.ti == dep_ti) { dep_vars.push_back(vi.var); dep_var_infos.push_back(&vi); }
                if (dep_vars.empty()) {
                    // dependency has no feasible window -> task cannot be scheduled
                    LinearExpr sum;
                    for (auto &v : task_vars) sum += v;
                    cp_model.AddEquality(sum, 0);
                    continue;
                }
                // sum(task) <= sum(dep)
                LinearExpr sum_task, sum_dep;
                for (auto &v : task_vars) sum_task += v;
                for (auto &v : dep_vars) sum_dep += v;
                cp_model.AddLessOrEqual(sum_task, sum_dep);

                // temporal: for each task var, dep must be earlier date/time
                for (auto *tvi : task_var_infos) {
                    const WindowInfo& w_task = windows[tvi->wi];
                    LinearExpr earlier_dep;
                    int earlier_cnt=0;
                    for (auto *dvi : dep_var_infos) {
                        const WindowInfo& w_dep = windows[dvi->wi];
                        if (w_dep.service_date < w_task.service_date ||
                            (w_dep.service_date == w_task.service_date && w_dep.start_time <= w_task.start_time)) {
                            earlier_dep += dvi->var;
                            earlier_cnt++;
                        }
                    }
                    if (earlier_cnt>0) {
                        cp_model.AddLessOrEqual(tvi->var, earlier_dep);
                    } else {
                        cp_model.AddEquality(tvi->var, 0);
                    }
                }
            }
        }

        // Solve with 5s 8 workers
        Model model;
        SatParameters params;
        params.set_max_time_in_seconds((double)time_limit);
        params.set_num_search_workers(8);
        // determinism & logging
        params.set_cp_model_presolve(true);
        params.set_log_search_progress(false);
        model.Add(NewSatParameters(params));

        CpSolverResponse response = SolveCpModel(cp_model.Build(), &model);

        std::string status_str = "UNKNOWN";
        // CpSolverStatus enum handling version-agnostic via string
        // Try to get status via response.status()
        try {
            auto s = response.status();
            if (s == CpSolverStatus::OPTIMAL) status_str = "OPTIMAL";
            else if (s == CpSolverStatus::FEASIBLE) status_str = "FEASIBLE";
            else if (s == CpSolverStatus::INFEASIBLE) status_str = "INFEASIBLE";
            else if (s == CpSolverStatus::MODEL_INVALID) status_str = "MODEL_INVALID";
            else status_str = "UNKNOWN";
        } catch (...) {
            status_str = "UNKNOWN";
        }

        if (status_str != "OPTIMAL" && status_str != "FEASIBLE") {
            py::dict res;
            res["status"] = status_str;
            res["reason"] = py::str("Solver status ")+ py::str(status_str);
            res["assignments"] = py::list();
            res["objective_value"] = 0;
            res["solver"] = "cpp-cp-sat";
            res["workers"] = 8;
            res["time_limit"] = time_limit;
            auto t1 = std::chrono::steady_clock::now();
            double rt = std::chrono::duration<double>(t1 - t0).count();
            res["solver_runtime"] = rt;
            return json_mod.attr("dumps")(res).cast<std::string>();
        }

        py::list assignments;
        int objective_value = 0;
        for (auto &vi : vars) {
            bool val = false;
            try {
                // New API: response.solution_value(vi.var) or Value()
                // Try Value first
                val = response.Value(vi.var) != 0;
            } catch (...) {
                try { val = SolutionIntegerValue(response, vi.var) != 0; } catch (...) { val = false; }
            }
            if (val) {
                py::dict a;
                a["task_id"] = tasks[vi.ti].id;
                a["window_id"] = windows[vi.wi].id;
                a["corridor_id"] = windows[vi.wi].corridor_id;
                a["service_date"] = windows[vi.wi].service_date;
                a["start_time"] = windows[vi.wi].start_time;
                a["end_time"] = windows[vi.wi].start_time + tasks[vi.ti].duration + tasks[vi.ti].setup;
                if (a["end_time"].cast<int>() > windows[vi.wi].end_time) a["end_time"] = windows[vi.wi].end_time;
                a["block_type"] = windows[vi.wi].block_type;
                a["priority_score"] = tasks[vi.ti].priority_score;
                a["department"] = tasks[vi.ti].department;
                assignments.append(a);
                objective_value += vi.net;
            }
        }

        py::dict res;
        res["status"] = status_str;
        res["assignments"] = assignments;
        res["objective_value"] = objective_value;
        res["solver"] = "cpp-cp-sat";
        res["workers"] = 8;
        res["time_limit"] = time_limit;
        auto t1 = std::chrono::steady_clock::now();
        double rt = std::chrono::duration<double>(t1 - t0).count();
        res["solver_runtime"] = rt;
        res["task_count"] = (int)tasks.size();
        res["window_count"] = (int)windows.size();
        res["feasible_pairs"] = (int)vars.size();
        res["scheduled"] = (int)py::len(assignments);
        return json_mod.attr("dumps")(res).cast<std::string>();
    } catch (const std::exception& e) {
        py::dict res;
        res["status"] = "ERROR";
        res["error"] = py::str(e.what());
        res["assignments"] = py::list();
        res["solver"] = "cpp-cp-sat";
        res["fallback"] = true;
        return json_mod.attr("dumps")(res).cast<std::string>();
    }
#else
    // Fallback greedy without OR-Tools (still C++ fast path)
    std::set<std::string> used_windows;
    std::map<std::string, std::set<std::string>> date_resource_used; // date -> set of resource ids
    std::set<std::string> scheduled_tasks;
    // dependency check helper: ensure deps scheduled earlier
    std::map<std::string, std::string> task_to_date; // task_id -> service_date

    // sort already done

    py::list assignments;
    int objective = 0;

    // Precompute feasible pairs sorted by net desc per task
    struct Pair { int ti; int wi; int net; };
    std::vector<Pair> pairs;
    for (size_t ti=0; ti<tasks.size(); ++ti)
        for (size_t wi=0; wi<windows.size(); ++wi)
            if (!hard_conflict(tasks[ti], windows[wi]))
                pairs.push_back({(int)ti,(int)wi, compute_net(tasks[ti], windows[wi])});
    std::sort(pairs.begin(), pairs.end(), [](const Pair& a, const Pair& b){ return a.net > b.net; });

    // Greedy by net globally
    for (auto &p : pairs) {
        const TaskInfo& t = tasks[p.ti];
        const WindowInfo& w = windows[p.wi];
        if (scheduled_tasks.count(t.id)) continue;
        if (used_windows.count(w.id)) continue;
        // resource check per date
        bool res_conf=false;
        for (auto &rid: t.resource_ids) if (date_resource_used[w.service_date].count(rid)) { res_conf=true; break; }
        if (res_conf) continue;
        // dependency check
        bool dep_ok=true;
        std::string earliest = "";
        for (auto &dep : dep_map[t.id]) {
            if (!scheduled_tasks.count(dep)) { dep_ok=false; break; }
            std::string dep_date = task_to_date[dep];
            if (dep_date > w.service_date) { dep_ok=false; break; }
            // if same date, need start_time ordering - approximate via window ordering; since we pick globally, we check existence
        }
        if (!dep_ok) continue;

        // assign
        py::dict a;
        a["task_id"] = t.id;
        a["window_id"] = w.id;
        a["corridor_id"] = w.corridor_id;
        a["service_date"] = w.service_date;
        a["start_time"] = w.start_time;
        int end = w.start_time + t.duration + t.setup;
        if (end > w.end_time) end = w.end_time;
        a["end_time"] = end;
        a["block_type"] = w.block_type;
        a["priority_score"] = t.priority_score;
        a["department"] = t.department;
        assignments.append(a);
        scheduled_tasks.insert(t.id);
        used_windows.insert(w.id);
        task_to_date[t.id]=w.service_date;
        for (auto &rid: t.resource_ids) date_resource_used[w.service_date].insert(rid);
        objective += p.net;
        if ((int)assignments.size() >= (int)windows.size()) break;
    }

    py::dict res;
    res["status"] = py::len(assignments) > 0 ? py::str("FEASIBLE") : py::str("INFEASIBLE");
    res["assignments"] = assignments;
    res["objective_value"] = objective;
    res["solver"] = "cpp-greedy-fallback";
    res["workers"] = 1;
    res["time_limit"] = time_limit;
    auto t1 = std::chrono::steady_clock::now();
    double rt = std::chrono::duration<double>(t1 - t0).count();
    res["solver_runtime"] = rt;
    res["note"] = "OR-Tools not found at compile time; used greedy fallback (still C++ via pybind11). Install libortools-dev for full CP-SAT.";
    return json_mod.attr("dumps")(res).cast<std::string>();
#endif
}

PYBIND11_MODULE(optimizer_cpp, m) {
    m.doc() = "RailBlock C++ CP-SAT heavy optimizer — deep module, small interface: solve(blocks_json, tasks_json, time_limit) -> json";
    // Primary interface as per spec: strings -> json string, 5s 8 workers
    m.def("solve", &solve_impl,
          py::arg("blocks_json"), py::arg("tasks_json"), py::arg("time_limit") = 5,
          "Solve with CP-SAT C++ (5s, 8 workers). Inputs are JSON strings, returns JSON string. Uses ortools/sat/cp_model.h when available, else greedy C++ fallback.");

    // Ergonomic overload: allow python objects (list/dict) directly, auto-JSON
    m.def("solve", [](py::object blocks, py::object tasks, int time_limit) -> std::string {
        py::module json = py::module::import("json");
        std::string bstr, tstr;
        if (py::isinstance<py::str>(blocks)) bstr = blocks.cast<std::string>();
        else bstr = json.attr("dumps")(blocks).cast<std::string>();
        if (py::isinstance<py::str>(tasks)) tstr = tasks.cast<std::string>();
        else tstr = json.attr("dumps")(tasks).cast<std::string>();
        return solve_impl(bstr, tstr, time_limit);
    }, py::arg("blocks"), py::arg("tasks"), py::arg("time_limit") = 5,
       "Overload: accepts Python lists/dicts directly (auto JSON-serialized).");

#if defined(HAS_ORTOOLS) && HAS_ORTOOLS
    m.attr("has_ortools") = true;
    m.attr("solver") = "ortools-cp-sat";
#else
    m.attr("has_ortools") = false;
    m.attr("solver") = "greedy-fallback";
#endif
    m.attr("workers") = 8;
    m.attr("time_limit_default") = 5;
}
