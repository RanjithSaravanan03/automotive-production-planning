# Resume and interview notes

## Project title

**Automotive Production Planning & Capacity Allocation**

Tools: Python, SQLite, SQL, HTML/CSS/JavaScript, scenario analysis.

## Compact resume bullets

- Built a Python–SQLite planning simulation for 28,000 automotive orders, tracking capacity, inventory and backlog.
- Diagnosed battery shortages and simulated transit changes yielding 422 more completions and a 2.23 pp on-time gain.
- Created an interactive dashboard comparing production, fulfilment, utilization and inventory across three scenarios.

Line fit depends on the CV font, margins and available width. Retain “simulated” in any result bullet. The dashboard is HTML-based; do not describe it as Power BI or Streamlit.

## Interview explanation

“I built a 14-day automotive planning simulation covering 28,000 customer orders. The planner respects component requirements, stock, supplier schedules, capacity and lead times, using an earliest-due-date feasible heuristic. I traced unused assembly capacity to battery material shortages. A hypothetical four-day reduction in component transit produced 422 more completed cars and 625 more on-time completions. The remaining gap was explained by a 1,130-battery supply deficit. I tested an additional opening battery buffer, verified results under two supplier policies, and built a dashboard showing the trade-offs. These are simulation findings; procurement and transport costs are not available.”

## Questions to prepare for

- Why do full-capacity days fail to clear backlog when demand also equals capacity?
- Why can raw-component arrivals not immediately satisfy car orders?
- How do quantity bounds differ from service/cost optimality?
- Why is 1,130 extra opening batteries not a general safety-stock recommendation?
- How do you verify inventory, capacity and fixed schedules?
- What changes would convert the fixed case into a reusable planner?
- Which costs and uncertainty data would you need before recommending a real intervention?
