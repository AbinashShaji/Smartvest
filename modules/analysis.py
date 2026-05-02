"""
analysis.py
-----------
Purpose : Handles the Dashboard and Analysis pages + their data APIs.
          ALL financial data now comes from the SQLite database — no more config lists.
"""

from flask import Blueprint, render_template, jsonify, redirect, url_for, request, session
import config
from utils.db import get_db_connection   # ← real database helper
import os
from datetime import datetime, timedelta
from typing import Any, Dict
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

plt.style.use("dark_background")

# Create the Analysis Blueprint so Flask can register these routes
analysis_bp = Blueprint('analysis', __name__)

STOCK_DAY_COLUMNS = [f"day{i}" for i in range(1, 11)]
CHART_FIGURE_FACE = "#000000"
CHART_AXES_FACE = (1, 1, 1, 0.03)
CHART_GRID_COLOR = (1, 1, 1, 0.08)
CHART_SPINE_COLOR = (1, 1, 1, 0.15)
CHART_TEXT_PRIMARY = "#ffffff"
CHART_TEXT_MUTED = "#a1a1aa"
CHART_TEAL = "#14b8a6"
CHART_SUCCESS = "#4ade80"
CHART_WARNING = "#fbbf24"
CHART_DANGER = "#f87171"
CHART_SECONDARY = "#60a5fa"
CHART_PALETTE = [
    CHART_TEAL,
    CHART_SUCCESS,
    CHART_WARNING,
    CHART_DANGER,
    CHART_SECONDARY,
    "#a78bfa",
]


def _new_chart_figure(figsize=(10, 6)):
    """Create a web-friendly figure that matches the dashboard dark theme."""
    fig, ax = plt.subplots(figsize=figsize, dpi=100, facecolor=CHART_FIGURE_FACE)
    ax.set_facecolor(CHART_AXES_FACE)
    return fig, ax


def _style_chart_axes(ax, title, xlabel="", ylabel=""):
    """Apply the shared dark-dashboard chart styling to an axes object."""
    ax.set_title(title, fontsize=16, color=CHART_TEXT_PRIMARY, fontweight="bold", pad=12)
    ax.set_xlabel(xlabel, fontsize=12, color=CHART_TEXT_MUTED, labelpad=8)
    ax.set_ylabel(ylabel, fontsize=12, color=CHART_TEXT_MUTED, labelpad=8)
    ax.tick_params(axis="both", colors=CHART_TEXT_PRIMARY, labelsize=10)
    ax.tick_params(axis="x", labelrotation=0)
    ax.grid(True, axis="both", color=CHART_GRID_COLOR, linestyle="--", linewidth=0.5, alpha=0.15, zorder=0)
    ax.set_axisbelow(True)

    for spine in ax.spines.values():
        spine.set_color(CHART_SPINE_COLOR)
        spine.set_linewidth(0.5)


def _finish_chart(fig, file_path):
    """Save a chart with layout padding that works well in the web UI."""
    fig.tight_layout(pad=1.5)
    fig.savefig(file_path, facecolor=CHART_FIGURE_FACE)
    plt.close(fig)


def _style_legend(legend):
    """Apply a dark, high-contrast style to any chart legend."""
    if legend is None:
        return

    legend.get_frame().set_facecolor((0, 0, 0, 0.35))
    legend.get_frame().set_edgecolor(CHART_SPINE_COLOR)
    legend.get_frame().set_linewidth(0.5)
    legend.set_frame_on(True)
    for text in legend.get_texts():
        text.set_color(CHART_TEXT_PRIMARY)
        text.set_fontsize(11)


def _coerce_float(value, default=0.0):
    """Convert a value to float safely, falling back to default on bad input."""
    try:
        if value is None:
            return default
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _sum_numeric(rows, key):
    """Sum a numeric key from SQLite rows without crashing on null values."""
    total = 0.0
    for row in rows:
        total += _coerce_float(row[key])
    return total


def _safe_stock_name(name):
    """Convert a stock name into a filename-friendly value."""
    cleaned = "".join(ch.lower() if ch.isalnum() else "_" for ch in str(name))
    cleaned = "_".join(part for part in cleaned.split("_") if part)
    return cleaned or "stock"


def load_stock_csv():
    """
    Purpose : Load stock data from the CSV file used by the upgrade.
    Output  : Pandas DataFrame with the expected stock columns.
    """
    required_columns = ["name"] + STOCK_DAY_COLUMNS
    try:
        stocks = pd.read_csv("data/stock.csv")
    except (FileNotFoundError, pd.errors.EmptyDataError):
        return pd.DataFrame(columns=required_columns)

    if "name" not in stocks.columns:
        stocks["name"] = ""

    for column in STOCK_DAY_COLUMNS:
        if column not in stocks.columns:
            stocks[column] = pd.NA

    return stocks.reindex(columns=required_columns)


def analyze_stock_rows(stocks, generate_charts=True):
    """
    Purpose : Classify each stock row and optionally generate a chart image.
    Input   : DataFrame with stock prices across day1..day10.
    Output  : (analysis list, status counts dictionary)
    """
    analyzed_stocks = []
    status_counts = {"Good": 0, "Bad": 0, "Stable": 0}

    if generate_charts:
        os.makedirs("static", exist_ok=True)

    for index, row in stocks.iterrows():
        stock_name = str(row["name"]).strip() or f"Stock {index + 1}"
        prices = [ _coerce_float(row[column]) for column in STOCK_DAY_COLUMNS ]
        change = float(prices[-1] - prices[0]) if prices else 0.0

        if change > 5:
            status = "Good"
        elif change < -5:
            status = "Bad"
        else:
            status = "Stable"

        status_counts[status] = status_counts[status] + 1

        chart_path = ""
        if generate_charts:
            safe_name = _safe_stock_name(stock_name)
            file_name = f"{safe_name}_stock.png"
            file_path = os.path.join("static", file_name)

            days = [f"Day {i}" for i in range(1, len(prices) + 1)]
            fig, ax = _new_chart_figure(figsize=(6, 3.5))
            ax.plot(days, prices, marker="o", linewidth=2.5, markersize=8, color=CHART_TEAL, label="Price")
            _style_chart_axes(ax, f"{stock_name} Stock Trend", "Day", "Price")
            legend = ax.legend(
                loc="best",
                frameon=True,
                framealpha=0.95,
                shadow=False,
            )
            _style_legend(legend)
            _finish_chart(fig, file_path)
            chart_path = "/static/" + file_name

        analyzed_stocks.append({
            "name": stock_name,
            "status": status,
            "change": round(change, 2),
            "prices": [float(price) for price in prices],
            "chart": chart_path,
        })

    return analyzed_stocks, status_counts


def get_risk_level(savings_rate):
    """Map savings rate to a beginner-friendly risk label."""
    if savings_rate < 20:
        return "Low"
    if savings_rate < 40:
        return "Medium"
    return "High"


def filter_recommended_stocks(stocks, risk_level):
    """Filter analyzed stocks by the chosen risk level."""
    allowed_status = {
        "Low": {"Stable"},
        "Medium": {"Stable", "Good"},
        "High": {"Good"},
    }.get(risk_level, {"Stable"})

    return [stock for stock in stocks if stock["status"] in allowed_status]


def classify_market_stock(percent_change):
    """
    Purpose : Classify a stock using percentage movement.
    Input   : percent_change as a float.
    Output  : Good, Bad, or Stable.
    """
    if percent_change > 5:
        return "Good"
    if percent_change < -5:
        return "Bad"
    return "Stable"


def _save_empty_chart(file_path, title, message):
    """Create a simple placeholder chart when no stock data is available."""
    fig, ax = _new_chart_figure(figsize=(10, 6))
    _style_chart_axes(ax, title)
    ax.text(0.5, 0.5, message, ha="center", va="center", color=CHART_TEXT_PRIMARY, fontsize=14, transform=ax.transAxes)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    _finish_chart(fig, file_path)


def _month_key_from_timestamp(value: pd.Timestamp) -> str:
    """Build a YYYY-MM key from a pandas timestamp."""
    return f"{value.year:04d}-{value.month:02d}"


def _month_label_from_key(month_key: str) -> str:
    """Convert a YYYY-MM key into a short readable label."""
    try:
        parsed = datetime.strptime(month_key + "-01", "%Y-%m-%d")
        return parsed.strftime("%b %Y")
    except ValueError:
        return month_key


def _build_month_series(df: pd.DataFrame, *, start_months_ago: int, count: int) -> list[dict]:
    """Build a consecutive monthly trend series with zero-filled gaps."""
    if count <= 0:
        return []

    today = datetime.now()
    month_keys: list[str] = []
    for offset in range(start_months_ago, start_months_ago - count, -1):
        shifted = (pd.Timestamp(today.year, today.month, 1) - pd.DateOffset(months=offset))
        month_keys.append(_month_key_from_timestamp(shifted))

    monthly_totals: dict[str, float] = {}
    if not df.empty:
        monthly_groups = df.groupby(df["date"].dt.to_period("M"))["amount"].sum()
        for period, amount in monthly_groups.items():
            monthly_totals[str(period)] = float(amount)

    series = []
    for month_key in month_keys:
        series.append({
            "month": month_key,
            "label": _month_label_from_key(month_key),
            "expense": round(monthly_totals.get(month_key, 0.0), 2),
        })
    return series


def _save_pie_chart(file_path, labels, values, title, empty_message):
    """Write a pie chart, falling back to a placeholder when there is no data."""
    if not labels or not values or sum(values) <= 0:
        _save_empty_chart(file_path, title, empty_message)
        return

    fig, ax = _new_chart_figure(figsize=(10, 6))
    colors = CHART_PALETTE[: len(values)]

    wedges, _, autotexts = ax.pie(
        values,
        labels=labels,
        autopct="%1.1f%%",
        startangle=90,
        counterclock=False,
        colors=colors,
        labeldistance=1.08,
        pctdistance=0.72,
        wedgeprops={"linewidth": 0.8, "edgecolor": CHART_FIGURE_FACE},
        textprops={"color": CHART_TEXT_PRIMARY, "fontsize": 12},
    )

    for autotext in autotexts:
        autotext.set_color(CHART_TEXT_PRIMARY)
        autotext.set_fontsize(12)

    if len(labels) > 3:
        legend_labels = [f"{label} ({value:,.0f})" for label, value in zip(labels, values)]
        legend = ax.legend(
            wedges,
            legend_labels,
            loc="upper left",
            bbox_to_anchor=(1.05, 1),
            frameon=True,
            framealpha=0.95,
            shadow=False,
        )
    else:
        legend = ax.legend(
            wedges,
            labels,
            loc="best",
            frameon=True,
            framealpha=0.95,
            shadow=False,
        )
    _style_legend(legend)

    ax.set_title(title, fontsize=16, color=CHART_TEXT_PRIMARY, fontweight="bold", pad=12)
    if len(labels) > 3:
        fig.tight_layout(pad=1.5, rect=(0, 0, 0.82, 1))
    else:
        fig.tight_layout(pad=1.5)
    fig.savefig(file_path, facecolor=CHART_FIGURE_FACE)
    plt.close(fig)


def _save_bar_chart(file_path, labels, values, title, empty_message):
    """Write a bar chart, falling back to a placeholder when there is no data."""
    if not labels or not values or sum(values) <= 0:
        _save_empty_chart(file_path, title, empty_message)
        return

    fig, ax = _new_chart_figure(figsize=(10, 6))
    y_positions = list(range(len(labels)))
    bars = ax.barh(y_positions, values, color=CHART_TEAL, edgecolor=CHART_SPINE_COLOR, linewidth=0.5, label="Expense")
    ax.set_yticks(y_positions)
    ax.set_yticklabels(labels, color=CHART_TEXT_PRIMARY, fontsize=10)
    ax.invert_yaxis()
    _style_chart_axes(ax, title, "Amount", "Category")
    ax.xaxis.set_major_locator(MaxNLocator(nbins=6))

    for bar, value in zip(bars, values):
        ax.text(
            bar.get_width(),
            bar.get_y() + bar.get_height() / 2,
            f" {value:,.0f}",
            va="center",
            ha="left",
            color=CHART_TEXT_PRIMARY,
            fontsize=10,
        )

    legend = ax.legend(loc="best", frameon=True, framealpha=0.95, shadow=False)
    _style_legend(legend)
    _finish_chart(fig, file_path)


def _save_line_chart(file_path, trend_data, title, empty_message):
    """Write a line chart or a placeholder when no trend data exists."""
    if not trend_data or not any(_coerce_float(item.get("expense")) > 0 for item in trend_data):
        _save_empty_chart(file_path, title, empty_message)
        return

    fig, ax = _new_chart_figure(figsize=(10, 6))
    labels = [item.get("label") or item.get("month") or "" for item in trend_data]
    values = [_coerce_float(item.get("expense")) for item in trend_data]
    ax.plot(labels, values, marker="o", linewidth=2.5, markersize=8, color=CHART_TEAL, label="Expense")
    _style_chart_axes(ax, title, "Month", "Amount")
    ax.xaxis.set_tick_params(labelrotation=0)
    ax.yaxis.set_major_locator(MaxNLocator(nbins=6))
    legend = ax.legend(
        loc="best",
        frameon=True,
        framealpha=0.95,
        shadow=False,
    )
    _style_legend(legend)
    _finish_chart(fig, file_path)


def _generate_financial_charts(current: Dict[str, Any], yearly: Dict[str, Any]) -> Dict[str, str]:
    """Generate and overwrite the financial charts used by the UI."""
    os.makedirs("static", exist_ok=True)

    category_chart = "static/current_pie.png"
    category_bar_chart = "static/current_category_bar.png"
    trend_chart = "static/current_trend.png"
    yearly_trend_chart = "static/yearly_trend.png"
    yearly_bar_chart = "static/yearly_expense_bar.png"

    category_breakdown = current.get("category_breakdown") or []
    sorted_category_breakdown = sorted(
        category_breakdown,
        key=lambda item: _coerce_float(item.get("amount")),
        reverse=True,
    )
    _save_pie_chart(
        category_chart,
        [str(item.get("category") or "Other") for item in sorted_category_breakdown],
        [_coerce_float(item.get("amount")) for item in sorted_category_breakdown],
        "Category Breakdown",
        "No category data yet",
    )

    _save_bar_chart(
        category_bar_chart,
        [str(item.get("category") or "Other") for item in sorted_category_breakdown[:8]],
        [_coerce_float(item.get("amount")) for item in sorted_category_breakdown[:8]],
        "Category vs Expense",
        "No category data yet",
    )

    _save_line_chart(
        trend_chart,
        current.get("trend_data") or [],
        "Monthly Spending Trend",
        "No spending trend yet",
    )

    _save_line_chart(
        yearly_trend_chart,
        yearly.get("trend_data") or [],
        "Yearly Spending Trend",
        "No yearly trend yet",
    )

    yearly_trend_data = yearly.get("trend_data") or []
    _save_bar_chart(
        yearly_bar_chart,
        [str(item.get("label") or item.get("month") or "Month") for item in yearly_trend_data],
        [_coerce_float(item.get("expense")) for item in yearly_trend_data],
        "Monthly Expense Comparison",
        "No yearly trend yet",
    )

    return {
        "current_pie": "/static/current_pie.png",
        "current_category_bar": "/static/current_category_bar.png",
        "current_trend": "/static/current_trend.png",
        "yearly_trend_chart": "/static/yearly_trend.png",
        "yearly_expense_bar": "/static/yearly_expense_bar.png",
        "category_chart": "/static/current_pie.png",
        "category_bar_chart": "/static/current_category_bar.png",
        "trend_chart": "/static/current_trend.png",
        "yearly_bar_chart": "/static/yearly_expense_bar.png",
    }


def _trend_direction(values: list[float]) -> str:
    """Classify a sequence as increasing, decreasing, or stable."""
    cleaned = [float(value) for value in values if _coerce_float(value) is not None]
    cleaned = [value for value in cleaned if value >= 0]
    if len(cleaned) < 2:
        return "stable"

    first = cleaned[0]
    last = cleaned[-1]
    if first <= 0 and last > 0:
        return "increasing"

    change = ((last - first) / first) * 100 if first > 0 else 0.0
    if change > 5:
        return "increasing"
    if change < -5:
        return "decreasing"
    return "stable"


def _coefficient_of_variation(values: list[float]) -> float:
    """Return a normalized volatility measure for expense series."""
    cleaned = [float(value) for value in values if value is not None]
    cleaned = [value for value in cleaned if value >= 0]
    if len(cleaned) < 2:
        return 0.0

    mean_value = sum(cleaned) / len(cleaned)
    if mean_value <= 0:
        return 0.0

    variance = sum((value - mean_value) ** 2 for value in cleaned) / len(cleaned)
    return (variance ** 0.5) / mean_value


def _safe_label_month(item: Dict[str, Any]) -> str:
    """Return a display label from a monthly point."""
    return item.get("label") or item.get("month") or "--"


def _build_pattern_analysis(current_values: list[float], current_expense: float, current_category_map: Dict[str, float], prev_category_map: Dict[str, float]) -> Dict[str, Any]:
    """
    Build a safe monthly spending pattern snapshot.
    This keeps the UI populated even when the dataset is small or empty.
    """
    direction = _trend_direction(current_values)
    volatility = _coefficient_of_variation(current_values) * 100

    recurring_spend = 0.0
    for category in set(current_category_map) & set(prev_category_map):
        recurring_spend += min(current_category_map.get(category, 0.0), prev_category_map.get(category, 0.0))

    fixed_ratio = round((recurring_spend / current_expense) * 100, 2) if current_expense > 0 else 0.0
    variable_ratio = round(100.0 - fixed_ratio, 2) if current_expense > 0 else 0.0

    if not current_values or current_expense <= 0:
        observation = "No spending data yet. Add a few expenses to reveal trend direction, fixed spend, and volatility."
        direction = "stable"
        volatility = 0.0
        fixed_ratio = 0.0
        variable_ratio = 0.0
    else:
        observation = (
            f"Spending is {direction} with {fixed_ratio:.1f}% fixed-like spend and {variable_ratio:.1f}% variable spend."
        )

    return {
        "direction": direction,
        "fixed_ratio": fixed_ratio,
        "variable_ratio": variable_ratio,
        "volatility": round(volatility, 2),
        "observation": observation,
    }


def _build_yearly_trend_analysis(monthly_breakdown: list[dict]) -> Dict[str, Any]:
    """
    Build a yearly trend snapshot from monthly totals only.
    This stays separate from the monthly pattern analysis helper.
    """
    if not monthly_breakdown:
        return {
            "direction": "stable",
            "spike_month": None,
            "lowest_month": None,
            "average_monthly_spend": 0.0,
            "volatility": 0.0,
            "month_over_month_change": 0.0,
            "monthly_changes": [],
            "observation": "No yearly data yet. Add expenses across the year to reveal a trend.",
        }

    monthly_expenses = [float(item.get("expense", 0.0) or 0.0) for item in monthly_breakdown]
    first_value = monthly_expenses[0] if monthly_expenses else 0.0
    last_value = monthly_expenses[-1] if monthly_expenses else 0.0

    if first_value <= 0 and last_value > 0:
        direction = "increasing"
    elif first_value > 0 and last_value <= 0:
        direction = "decreasing"
    elif first_value == last_value:
        direction = "stable"
    else:
        change = ((last_value - first_value) / first_value) * 100 if first_value > 0 else 0.0
        if change > 5:
            direction = "increasing"
        elif change < -5:
            direction = "decreasing"
        else:
            direction = "stable"

    spike_month = max(monthly_breakdown, key=lambda item: float(item.get("expense", 0.0) or 0.0))
    lowest_month = min(monthly_breakdown, key=lambda item: float(item.get("expense", 0.0) or 0.0))
    average_monthly_spend = sum(monthly_expenses) / len(monthly_expenses) if monthly_expenses else 0.0
    volatility = _coefficient_of_variation(monthly_expenses) * 100

    monthly_changes = []
    for index in range(1, len(monthly_breakdown)):
        previous_value = float(monthly_breakdown[index - 1].get("expense", 0.0) or 0.0)
        current_value = float(monthly_breakdown[index].get("expense", 0.0) or 0.0)
        if previous_value > 0:
            change_percent = round(((current_value - previous_value) / previous_value) * 100, 2)
        elif current_value > 0:
            change_percent = 100.0
        else:
            change_percent = 0.0
        monthly_changes.append({
            "label": monthly_breakdown[index].get("label") or monthly_breakdown[index].get("month") or "--",
            "change_percent": change_percent,
            "direction": "up" if change_percent > 0 else "down" if change_percent < 0 else "flat",
        })

    latest_change = monthly_changes[-1]["change_percent"] if monthly_changes else 0.0
    observation = (
        f"Yearly trend is {direction} with volatility at {volatility:.1f}%."
        f" Spike month: {(spike_month or {}).get('label') or '--'}."
        f" Lowest month: {(lowest_month or {}).get('label') or '--'}."
    )

    return {
        "direction": direction,
        "spike_month": spike_month,
        "lowest_month": lowest_month,
        "average_monthly_spend": round(average_monthly_spend, 2),
        "volatility": round(volatility, 2),
        "month_over_month_change": round(latest_change, 2),
        "monthly_changes": monthly_changes[-5:],
        "observation": observation,
    }


def calculate_avg_savings(monthly_income: float, expense_history: list[float]) -> float:
    """
    Purpose : Calculate average savings over the last N months.
    Input   : monthly_income (float), expense_history (list of monthly expense totals).
    Output  : Average monthly savings (income − expense) as a float.
    """
    if not expense_history or monthly_income <= 0:
        return 0.0

    # Calculate savings for each month: income minus that month's expense
    savings_per_month = [monthly_income - expense for expense in expense_history]
    return sum(savings_per_month) / len(savings_per_month)


def calculate_savings_volatility(monthly_income: float, expense_history: list[float]) -> float:
    """
    Purpose : Measure how stable the user's savings are month-to-month.
    Input   : monthly_income (float), expense_history (list of monthly expense totals).
    Output  : Coefficient of variation (0 = perfectly stable, higher = more volatile).
    """
    if not expense_history or monthly_income <= 0 or len(expense_history) < 2:
        return 0.0

    # Convert expenses into savings values
    savings_per_month = [monthly_income - expense for expense in expense_history]

    # Calculate mean savings
    mean_savings = sum(savings_per_month) / len(savings_per_month)
    if mean_savings <= 0:
        return 1.0  # Fully unstable — no positive average savings

    # Calculate standard deviation
    variance = sum((s - mean_savings) ** 2 for s in savings_per_month) / len(savings_per_month)
    std_dev = variance ** 0.5

    # Coefficient of variation = std_dev / mean
    return std_dev / mean_savings


def calculate_emergency_fund(
    monthly_income: float,
    avg_monthly_expense: float,
    current_savings: float,
    manual_target: float = 0.0,
) -> Dict[str, Any]:
    """
    Purpose : Evaluate the user's emergency-fund readiness.
    Input   : monthly_income, avg_monthly_expense, current_savings, optional manual_target.
    Output  : Dictionary with target, current, remaining, progress percent, and status.
    """
    # Target = monthly salary x selected months, or the default 2-month target.
    monthly_salary = max(0.0, monthly_income)
    auto_target = monthly_salary * 2.0
    target = manual_target if manual_target > 0 else auto_target

    # Remaining amount needed
    remaining = max(0.0, target - current_savings)

    # Progress is based on the target amount, not coverage months.
    progress = (current_savings / target) * 100 if target > 0 else 0.0
    progress = max(0.0, min(100.0, progress))

    # Status classification based on progress percentage.
    if progress < 25:
        status = "CRITICAL"
        tone = "red"
    elif progress <= 75:
        status = "MODERATE"
        tone = "orange"
    else:
        status = "GOOD"
        tone = "green"

    return {
        "target": round(target, 2),
        "current": round(current_savings, 2),
        "remaining": round(remaining, 2),
        "progress_percent": round(progress, 2),
        "monthly_salary": round(monthly_salary, 2),
        "status": status,
        "tone": tone,
    }


def detect_spike_categories(category_change: list) -> list:
    """
    Purpose : Find categories that spiked compared to the previous month.
    Input   : category_change list from get_analysis_data.
    Output  : List of {category, increase, percent} for categories that went up >15%.
    """
    spikes = []
    for item in category_change:
        change_pct = item.get("change_percent", 0.0)
        direction = item.get("direction", "flat")
        # Only flag categories that increased more than 15% vs previous month
        if direction == "up" and change_pct > 15:
            spikes.append({
                "category": item["category"],
                "increase": item["change_amount"],
                "percent": change_pct,
            })
    return spikes


def get_analysis_data(user_id=None):
    """Build the single source of truth for the analysis page."""
    if user_id is None:
        current_user = config.get_current_user() or {}
        user_id = current_user.get("user_id")

    if user_id is None:
        raise ValueError("Login required")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT amount, category, date FROM expenses WHERE user_id = ?",
        (user_id,)
    )
    expense_rows = [dict(row) for row in cursor.fetchall()]

    cursor.execute(
        "SELECT amount FROM income WHERE user_id = ? ORDER BY id DESC LIMIT 1",
        (user_id,)
    )
    income_row = cursor.fetchone()
    monthly_income = _coerce_float(income_row["amount"]) if income_row is not None else 0.0
    conn.close()

    df = pd.DataFrame(expense_rows, columns=["amount", "category", "date"])
    if not df.empty:
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)
        df["category"] = df["category"].fillna("Other").astype(str).str.strip()
        df["category"] = df["category"].replace("", "Other")
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"])
        df = df.sort_values(by="date", ascending=False)

    now = datetime.now()
    prev_month_date = now.replace(day=1) - timedelta(days=1)

    if not df.empty:
        df_current = df[
            (df["date"].dt.month == now.month) &
            (df["date"].dt.year == now.year)
        ]
        df_prev = df[
            (df["date"].dt.month == prev_month_date.month) &
            (df["date"].dt.year == prev_month_date.year)
        ]
    else:
        df_current = df
        df_prev = df

    current_expense = float(df_current["amount"].sum()) if not df_current.empty else 0.0
    prev_expense = float(df_prev["amount"].sum()) if not df_prev.empty else 0.0
    savings = monthly_income - current_expense
    savings_rate = (savings / monthly_income) * 100 if monthly_income > 0 else 0.0
    change_percent = ((current_expense - prev_expense) / prev_expense) * 100 if prev_expense > 0 else 0.0

    current_category_map: Dict[str, float] = {}
    prev_category_map: Dict[str, float] = {}
    category_breakdown = []
    category_change = []
    top_category = None
    top_category_percent = 0.0

    if not df_current.empty:
        current_totals = (
            df_current.groupby("category")["amount"]
            .sum()
            .sort_values(ascending=False)
        )
        if not current_totals.empty:
            top_category = current_totals.idxmax()
            for category, amount in current_totals.items():
                value = round(float(amount), 2)
                current_category_map[category] = value
                percent = round((value / current_expense) * 100, 2) if current_expense > 0 else 0.0
                category_breakdown.append({
                    "category": category,
                    "amount": value,
                    "percent": percent,
                })
                if category == top_category:
                    top_category_percent = percent

    if not df_prev.empty:
        prev_totals = df_prev.groupby("category")["amount"].sum().sort_values(ascending=False)
        for category, amount in prev_totals.items():
            prev_category_map[category] = round(float(amount), 2)

    category_names = sorted(set(current_category_map) | set(prev_category_map), key=lambda name: max(current_category_map.get(name, 0.0), prev_category_map.get(name, 0.0)), reverse=True)
    for category in category_names:
        current_amount = current_category_map.get(category, 0.0)
        previous_amount = prev_category_map.get(category, 0.0)
        delta = round(current_amount - previous_amount, 2)
        if previous_amount > 0:
            delta_percent = round((delta / previous_amount) * 100, 2)
        elif current_amount > 0:
            delta_percent = 100.0
        else:
            delta_percent = 0.0
        category_change.append({
            "category": category,
            "current_amount": current_amount,
            "previous_amount": previous_amount,
            "change_amount": delta,
            "change_percent": delta_percent,
            "direction": "up" if delta > 0 else "down" if delta < 0 else "flat",
        })

    current_trend_data = _build_month_series(df, start_months_ago=5, count=6)
    yearly_trend_data = []
    if not df.empty:
        monthly_expense = (
            df.groupby(df["date"].dt.to_period("M"))["amount"]
            .sum()
            .sort_index()
        )
        for period, amount in monthly_expense.items():
            yearly_trend_data.append({
                "month": str(period),
                "label": period.strftime("%b %Y"),
                "expense": round(float(amount), 2),
            })

    months_count = int(df["date"].dt.to_period("M").nunique()) if not df.empty else 0
    total_income = monthly_income * months_count
    total_expense = float(df["amount"].sum()) if not df.empty else 0.0
    total_savings = total_income - total_expense

    # ── Phase 2: Build last-3-months expense history for savings analysis ──
    last_3_expenses: list[float] = []  # expense total for each of the last 3 months
    for offset in range(2, -1, -1):    # 2, 1, 0 → three months ending at current month
        shifted = (pd.Timestamp(now.year, now.month, 1) - pd.DateOffset(months=offset))
        mk = _month_key_from_timestamp(shifted)
        month_total = 0.0
        if not df.empty:
            mask = (
                (df["date"].dt.month == shifted.month) &
                (df["date"].dt.year == shifted.year)
            )
            month_total = float(df.loc[mask, "amount"].sum())
        last_3_expenses.append(month_total)

    avg_savings = calculate_avg_savings(monthly_income, last_3_expenses)
    savings_vol = calculate_savings_volatility(monthly_income, last_3_expenses)
    avg_monthly_expense = sum(last_3_expenses) / len(last_3_expenses) if last_3_expenses else 0.0

    # Check for a backend EF override stored in session.
    ef_manual_months = 0.0
    try:
        ef_manual_months = float(session.get("ef_manual_months", 0.0))
    except (TypeError, ValueError):
        ef_manual_months = 0.0

    # Backward compatibility for older sessions that stored a raw target amount.
    ef_manual_target = 0.0
    try:
        ef_manual_target = float(session.get("ef_manual_target", 0.0))
    except (TypeError, ValueError):
        ef_manual_target = 0.0

    if ef_manual_months > 0 and monthly_income > 0:
        ef_manual_target = monthly_income * ef_manual_months

    emergency = calculate_emergency_fund(
        monthly_income, avg_monthly_expense, savings,
        manual_target=ef_manual_target,
    )
    if ef_manual_months > 0:
        emergency["selected_months"] = round(ef_manual_months, 2)
    elif monthly_income > 0 and emergency.get("target", 0) > 0:
        emergency["selected_months"] = round(emergency["target"] / monthly_income, 2)
    else:
        emergency["selected_months"] = 0.0

    best_month = None
    worst_month = None
    if yearly_trend_data:
        monthly_savings_rows = [
            {
                **item,
                "savings": round(monthly_income - float(item["expense"]), 2),
            }
            for item in yearly_trend_data
        ]
        best_month = max(monthly_savings_rows, key=lambda item: item["savings"])
        worst_month = max(monthly_savings_rows, key=lambda item: item["expense"])
    else:
        monthly_savings_rows = []

    current_values = [item["expense"] for item in current_trend_data]
    yearly_values = [item["expense"] for item in yearly_trend_data]
    current_direction = _trend_direction(current_values)
    yearly_direction = _trend_direction(yearly_values)
    volatility = _coefficient_of_variation(current_values)
    yearly_volatility = _coefficient_of_variation(yearly_values)

    pattern_analysis = _build_pattern_analysis(current_values, current_expense, current_category_map, prev_category_map)

    if monthly_income <= 0:
        savings_condition = "Income is missing, so savings analysis is limited."
    elif savings_rate <= 0:
        savings_condition = "Savings are negative this month."
    elif savings_rate < 20:
        savings_condition = "Savings are below a healthy range."
    else:
        savings_condition = "Savings are in a healthy range."

    if monthly_income <= 0:
        current_insight = (
            "Monthly income is not set yet.\n"
            "Spending cannot be compared against savings until income is available.\n"
            "Set income to unlock more precise guidance."
        )
    else:
        current_insight = (
            f"Change vs last month: {'+' if change_percent > 0 else ''}{change_percent:.1f}%.\n"
            f"Top category impact: {top_category or 'No dominant category'} accounts for {top_category_percent:.1f}% of current spending.\n"
            f"Savings condition: {savings_condition}"
        )

    if savings_rate < 0:
        alert = {
            "label": "Risk",
            "tone": "red",
            "text": "You are overspending. Reduce discretionary spending immediately.",
        }
    elif savings_rate < 20:
        alert = {
            "label": "Watch",
            "tone": "yellow",
            "text": "Savings are low. Protect core categories and trim variable spend.",
        }
    else:
        alert = {
            "label": "Healthy",
            "tone": "green",
            "text": "Savings are on track. Keep recurring transfers consistent.",
        }

    cost_cutting = []
    for item in category_breakdown[:3]:
        potential = round(item["amount"] * 0.15, 2)
        cost_cutting.append({
            "category": item["category"],
            "current_amount": item["amount"],
            "potential_savings": potential,
            "note": f"Target a 15% reduction in {item['category']}.",
        })

    if savings_rate < 0:
        efficiency_label = "RISK"
        efficiency_tone = "red"
        efficiency_text = "Savings are negative and need immediate correction."
    elif savings_rate < 20:
        efficiency_label = "LOW"
        efficiency_tone = "yellow"
        efficiency_text = "Savings are below the ideal range."
    elif savings_rate <= 35:
        efficiency_label = "GOOD"
        efficiency_tone = "green"
        efficiency_text = "Savings are within a healthy range."
    else:
        efficiency_label = "GOOD"
        efficiency_tone = "green"
        efficiency_text = "Savings are strong. Keep the current structure."

    risk = {
        "overspending_warning": "Spending is higher than income." if savings < 0 else "",
        "low_savings_alert": "Savings are below 20%." if savings_rate < 20 else "",
        "volatility_warning": "Spending is volatile month to month." if volatility >= 0.35 else "",
    }

    if savings < 0:
        current_verdict = "Immediate action required: spending is above income."
    elif savings_rate < 20 or volatility >= 0.35:
        current_verdict = "Caution: tighten variable spending and rebuild savings momentum."
    else:
        current_verdict = "Healthy month: spending is controlled and savings behavior is strong."

    current_tip = "Trim the top category first, then redirect that amount into savings."
    if cost_cutting:
        current_tip = f"Reduce {cost_cutting[0]['category']} by about {cost_cutting[0]['potential_savings']:.2f} and move it to savings."

    current_detailed = {
        "category_breakdown": category_breakdown,
        "category_change": category_change[:5],
        "pattern_analysis": pattern_analysis,
        "cost_cutting": cost_cutting,
        "savings_efficiency": {
            "current_rate": round(savings_rate, 2),
            "ideal_min": 20.0,
            "ideal_max": 35.0,
            "label": efficiency_label,
            "tone": efficiency_tone,
            "text": efficiency_text,
        },
        "risk": risk,
        "verdict": current_verdict,
    }

    if yearly_trend_data:
        yearly_monthly_breakdown = []
        for item in yearly_trend_data:
            yearly_monthly_breakdown.append({
                "month": item["month"],
                "label": item["label"],
                "expense": item["expense"],
                "savings": round(monthly_income - item["expense"], 2),
            })
        yearly_category_totals = (
            df.groupby("category")["amount"]
            .sum()
            .sort_values(ascending=False)
        )
        top_yearly_category = None
        if not yearly_category_totals.empty:
            top_yearly_category = {
                "category": yearly_category_totals.idxmax(),
                "amount": round(float(yearly_category_totals.max()), 2),
                "share": round((float(yearly_category_totals.max()) / total_expense) * 100, 2) if total_expense > 0 else 0.0,
            }
        yearly_trend_analysis = _build_yearly_trend_analysis(yearly_monthly_breakdown)
    else:
        yearly_monthly_breakdown = []
        top_yearly_category = None
        yearly_trend_analysis = _build_yearly_trend_analysis([])

    yearly_savings_rate = (total_savings / total_income) * 100 if total_income > 0 else 0.0
    yearly_score = 100
    yearly_score -= min(35, max(0, (1 - max(yearly_savings_rate, 0) / 40) * 35))
    yearly_score -= min(20, yearly_trend_analysis["volatility"] * 0.4)
    yearly_score -= 8 if yearly_direction == "increasing" else 0
    yearly_score = round(max(0, min(100, yearly_score)))

    if yearly_score >= 80:
        yearly_verdict = "Excellent yearly performance with strong discipline."
    elif yearly_score >= 60:
        yearly_verdict = "Good yearly performance with some room to optimize."
    elif yearly_score >= 40:
        yearly_verdict = "Moderate yearly performance. Stabilize expenses and improve consistency."
    else:
        yearly_verdict = "Weak yearly performance. Review recurring spend and build a tighter plan."

    optimization = []
    if top_yearly_category:
        optimization.append({
            "category": top_yearly_category["category"],
            "potential_savings": round(top_yearly_category["amount"] * 0.1, 2),
            "note": "Top yearly category offers the clearest reduction opportunity.",
        })
    for item in sorted(category_change, key=lambda row: abs(row["change_amount"]), reverse=True)[:2]:
        if item["change_amount"] > 0:
            optimization.append({
                "category": item["category"],
                "potential_savings": round(item["change_amount"] * 0.5, 2),
                "note": "Reduce the recent increase before it compounds.",
            })

    yearly_insight = (
        f"Yearly trend: {yearly_trend_analysis['direction']} with volatility at {yearly_trend_analysis['volatility']:.1f}%.\n"
        f"Performance summary: total savings are {round(total_savings, 2):.2f} across {months_count} months.\n"
        f"Best month: {(best_month or {}).get('label') or '--'} | Worst month: {(worst_month or {}).get('label') or '--'}."
    )

    yearly_detailed = {
        "monthly_breakdown": yearly_monthly_breakdown,
        "trend_analysis": yearly_trend_analysis,
        "best_month": best_month,
        "worst_month": worst_month,
        "category_dominance": top_yearly_category,
        "consistency": {
            "label": "stable" if yearly_trend_analysis["volatility"] < 25 else "unstable",
            "tone": "green" if yearly_trend_analysis["volatility"] < 25 else "yellow",
            "variance": yearly_trend_analysis["volatility"],
            "text": "Monthly expenses are relatively steady." if yearly_trend_analysis["volatility"] < 25 else "Monthly expenses fluctuate significantly.",
        },
        "optimization": optimization,
        "score": yearly_score,
        "savings_rate": round(yearly_savings_rate, 2),
        "verdict": yearly_verdict,
    }

    current = {
        "income": round(monthly_income, 2),
        "expense": round(current_expense, 2),
        "savings": round(savings, 2),
        "savings_rate": round(savings_rate, 2),
        "prev_expense": round(prev_expense, 2),
        "change_percent": round(change_percent, 2),
        "top_category": top_category,
        "category_breakdown": category_breakdown,
        "trend_data": current_trend_data,
        "insight": current_insight,
        "tip": current_tip,
        "alert": alert,
        "detailed": current_detailed,
    }

    yearly = {
        "months_count": months_count,
        "total_income": round(total_income, 2),
        "total_expense": round(total_expense, 2),
        "total_savings": round(total_savings, 2),
        "best_month": best_month,
        "worst_month": worst_month,
        "trend_data": yearly_trend_data,
        "insight": yearly_insight,
        "detailed": yearly_detailed,
    }

    charts = _generate_financial_charts(current, yearly)

    # ── savings_behavior + emergency fund sections ──
    # Determine savings trend direction from the 3-month history
    savings_history_values = [monthly_income - e for e in last_3_expenses]
    if len(savings_history_values) >= 2:
        if savings_history_values[-1] > savings_history_values[0]:
            savings_trend = "increasing"
        elif savings_history_values[-1] < savings_history_values[0]:
            savings_trend = "decreasing"
        else:
            savings_trend = "flat"
    else:
        savings_trend = "flat"

    # Detect which categories caused spending spikes
    spike_categories = detect_spike_categories(category_change)

    savings_behavior = {
        "avg_savings": round(avg_savings, 2),
        "volatility": round(savings_vol, 4),
        "stable": savings_vol < 0.30,
        "trend": savings_trend,
        "spike_categories": spike_categories,
        "history": [
            {
                "month": _month_key_from_timestamp(
                    pd.Timestamp(now.year, now.month, 1) - pd.DateOffset(months=2 - i)
                ),
                "expense": round(last_3_expenses[i], 2),
                "savings": round(monthly_income - last_3_expenses[i], 2),
            }
            for i in range(len(last_3_expenses))
        ],
    }

    return {
        "current": current,
        "yearly": yearly,
        "charts": charts,
        "savings_behavior": savings_behavior,
        "emergency": emergency,
    }


def build_market_metrics():
    """
    Purpose : Analyze data/stock.csv and build admin market metrics.
    Output  : Dictionary with counts, market status, top movers, and chart paths.
    """
    stock_frame = load_stock_csv()
    os.makedirs("static", exist_ok=True)

    stock_rows = []
    good_count = 0
    bad_count = 0
    stable_count = 0

    if not stock_frame.empty:
        for index, row in stock_frame.iterrows():
            stock_name = str(row["name"]).strip() or f"Stock {index + 1}"
            day1 = pd.to_numeric(row["day1"], errors="coerce")
            day10 = pd.to_numeric(row["day10"], errors="coerce")

            day1_value = float(day1) if pd.notna(day1) else 0.0
            day10_value = float(day10) if pd.notna(day10) else 0.0

            if day1_value != 0:
                percent_change = ((day10_value - day1_value) / day1_value) * 100
            else:
                percent_change = 0.0

            status = classify_market_stock(percent_change)
            if status == "Good":
                good_count += 1
            elif status == "Bad":
                bad_count += 1
            else:
                stable_count += 1

            stock_rows.append({
                "name": stock_name,
                "day1": round(day1_value, 2),
                "day10": round(day10_value, 2),
                "percent_change": round(percent_change, 2),
                "status": status,
            })

    total_count = len(stock_rows)
    if total_count == 0:
        market_status = "No market data available"
    elif good_count > bad_count:
        market_status = "Growth"
    elif bad_count > good_count:
        market_status = "Down"
    else:
        market_status = "Stable"

    top_gainers = sorted(stock_rows, key=lambda item: item["percent_change"], reverse=True)[:5]
    top_losers = sorted(stock_rows, key=lambda item: item["percent_change"])[:5]

    trend_chart_path = "static/market_trend.png"
    summary_chart_path = "static/market_summary.png"

    if not stock_frame.empty:
        day_columns = [f"day{i}" for i in range(1, 11)]
        daily_average = stock_frame[day_columns].apply(pd.to_numeric, errors="coerce").fillna(0).mean(axis=0)
        x_values = list(range(1, 11))

        fig, ax = _new_chart_figure(figsize=(10, 6))
        ax.plot(x_values, daily_average.values, marker="o", linewidth=2.5, markersize=8, color=CHART_TEAL, label="Average Price")
        _style_chart_axes(ax, "Market Trend", "Day", "Average Price")
        ax.set_xticks(x_values)
        ax.set_xticklabels([f"Day {i}" for i in x_values], rotation=0)
        ax.yaxis.set_major_locator(MaxNLocator(nbins=6))
        legend = ax.legend(
            loc="best",
            frameon=True,
            framealpha=0.95,
            shadow=False,
        )
        _style_legend(legend)
        _finish_chart(fig, trend_chart_path)
    else:
        _save_empty_chart(trend_chart_path, "Market Trend", "No stock data available")

    fig, ax = _new_chart_figure(figsize=(10, 6))
    categories = ["Good", "Bad", "Stable"]
    counts = [good_count, bad_count, stable_count]
    colors = [CHART_SUCCESS, CHART_DANGER, CHART_TEXT_MUTED]
    bars = ax.bar(categories, counts, color=colors, edgecolor=CHART_SPINE_COLOR, linewidth=0.5, zorder=2)
    _style_chart_axes(ax, "Market Summary", "Classification", "Count")
    ax.yaxis.set_major_locator(MaxNLocator(nbins=6))
    for bar in bars:
        height = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            height,
            f"{height:.0f}",
            ha="center",
            va="bottom",
            color=CHART_TEXT_PRIMARY,
            fontsize=10,
        )
    _finish_chart(fig, summary_chart_path)

    summary = (
        f"Analysed {total_count} stocks from data/stock.csv. "
        f"Good: {good_count}, Bad: {bad_count}, Stable: {stable_count}."
    )

    return {
        "summary": summary,
        "market_status": market_status,
        "counts": {
            "good": good_count,
            "bad": bad_count,
            "stable": stable_count,
            "total": total_count,
        },
        "top_gainers": top_gainers,
        "top_losers": top_losers,
        "charts": {
            "trend": "/static/market_trend.png",
            "summary": "/static/market_summary.png",
        },
    }


def get_user_financial_snapshot(user_id):
    """
    Purpose : Calculate the current user's income, expenses, savings and risk level.
    Output  : Dictionary used by investment-related APIs.

    FIX (Phase 1): Now uses CURRENT-MONTH expenses only, not total history.
    This prevents inflated "total_expenses" from corrupting savings/risk calculations.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # ── Get current-month expenses only ──
    now = datetime.now()
    month_start = now.strftime("%Y-%m-01")
    next_month = (now.replace(day=1) + timedelta(days=32)).replace(day=1)
    month_end = next_month.strftime("%Y-%m-%d")

    cursor.execute(
        "SELECT amount FROM expenses WHERE user_id = ? AND date >= ? AND date < ?",
        (user_id, month_start, month_end),
    )
    expense_rows = cursor.fetchall()
    current_month_expenses = _sum_numeric(expense_rows, "amount")

    # ── Get latest monthly income ──
    cursor.execute(
        "SELECT amount FROM income WHERE user_id = ? ORDER BY id DESC LIMIT 1",
        (user_id,),
    )
    income_row = cursor.fetchone()
    monthly_income = _coerce_float(income_row["amount"]) if income_row is not None else 0.0

    conn.close()

    # ── Calculate savings using monthly figures only ──
    savings = monthly_income - current_month_expenses

    if monthly_income > 0:
        savings_rate = (savings / monthly_income) * 100
    else:
        savings_rate = 0.0

    risk_level = get_risk_level(savings_rate)

    # ── Investment suggestion based on monthly savings ──
    if savings <= 0:
        suggestion = "You have no savings. Focus on reducing expenses."
    elif savings_rate < 20:
        suggestion = "Your savings are low. Build an emergency fund first."
    elif savings_rate < 40:
        suggestion = "You can start investing in mutual funds or SIP."
    else:
        suggestion = "You have strong savings. Consider stocks and diversified investments."

    return {
        "total_expenses": round(current_month_expenses, 2),
        "income": round(monthly_income, 2),
        "savings": round(savings, 2),
        "savings_rate": round(savings_rate, 2),
        "risk_level": risk_level,
    }


# =============================================================================
# UI PAGE ROUTES  (return HTML pages)
# =============================================================================

@analysis_bp.route("/dashboard")
def dashboard():
    """
    Purpose : Renders the central Intelligence Dashboard page.
    Input   : None (user_id is taken from the session automatically).
    Output  : HTML page, or redirect to login if not logged in.
    """
    if not config.is_logged_in():
        return redirect(url_for("auth.login"))

    return render_template(
        "user/dashboard.html",
        active_page="dashboard",
        user=config.get_current_user(),
    )


@analysis_bp.route("/analysis")
def analysis_page():
    """
    Purpose : Renders the Financial Efficiency Report page.
    Input   : None.
    Output  : HTML page, or redirect to login if not logged in.
    """
    if not config.is_logged_in():
        return redirect(url_for("auth.login"))

    return render_template(
        "user/analysis.html",
        active_page="analysis",
        user=config.get_current_user(),
    )


# =============================================================================
# ANALYSIS API ROUTES  (return JSON data for the frontend charts/cards)
# =============================================================================

@analysis_bp.route("/api/analysis/data")
def api_dashboard_data():
    if not config.is_logged_in():
        return jsonify({"status": "error", "message": "Login required"}), 401

    try:
        user_id = config.get_current_user()["user_id"]
        analysis_data = get_analysis_data(user_id)
        return jsonify({"status": "success", "data": analysis_data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400


@analysis_bp.route("/api/dashboard")
def api_dashboard_alias():
    """Compatibility alias for older clients expecting /api/dashboard."""
    return api_dashboard_data()


@analysis_bp.route("/api/analysis/report")
def api_expense_analysis():
    if not config.is_logged_in():
        return jsonify({"status": "error", "message": "Login required"}), 401

    try:
        user_id = config.get_current_user()["user_id"]
        analysis_data = get_analysis_data(user_id)
        current = analysis_data["current"]

        if current["savings_rate"] < 0:
            summary_text = "You are overspending this month."
        elif current["savings_rate"] < 20:
            summary_text = "Your savings are low."
        else:
            summary_text = "You are saving well."

        return jsonify({
            "status": "success",
            "data": {
                "summary": summary_text,
                "total_expenses": round(current["expense"], 2),
                "income": round(current["income"], 2),
                "analysis": analysis_data,
            },
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400


@analysis_bp.route("/api/analysis")
def api_analysis_alias():
    """Compatibility alias for older clients expecting /api/analysis."""
    return api_expense_analysis()


@analysis_bp.route("/api/analysis/dataframe")
def api_expenses_dataframe():
    if not config.is_logged_in():
        return jsonify({"status": "error", "message": "Login required"}), 401

    try:
        user_id = config.get_current_user()["user_id"]
        return jsonify({"status": "success", "data": get_analysis_data(user_id)})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400


@analysis_bp.route("/api/analysis/ef-override", methods=["POST"])
def api_ef_override():
    """
    Purpose : Store a custom emergency fund target in the user's session.
    Input   : JSON body with "months" (float or int).
    Output  : JSON confirmation with the refreshed emergency-fund data.
    """
    if not config.is_logged_in():
        return jsonify({"status": "error", "message": "Login required"}), 401

    data = request.get_json(silent=True) or {}
    try:
        months = float(data.get("months", 0))
        if months <= 0:
            return jsonify({"status": "error", "message": "Invalid target value"}), 400

        user_id = config.get_current_user()["user_id"]
        analysis_data = get_analysis_data(user_id)
        monthly_salary = _coerce_float(analysis_data.get("current", {}).get("income", 0.0))

        if monthly_salary <= 0:
            return jsonify({"status": "error", "message": "Emergency fund target cannot be updated yet"}), 400

        target = round(months * monthly_salary, 2)
        session["ef_manual_months"] = months
        session.pop("ef_manual_target", None)

        updated_data = get_analysis_data(user_id)
        return jsonify({
            "status": "success",
            "data": {
                "months": months,
                "target": target,
                "emergency": updated_data.get("emergency", {}),
            },
        })
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "Invalid target value"}), 400
