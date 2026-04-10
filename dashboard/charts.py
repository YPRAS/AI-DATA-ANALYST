"""Dashboard KPI and chart builders."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DATA_PATH = _PROJECT_ROOT / "raw_data" / "cleaned_data.csv"

_ENGAGEMENT_SCORE = {
    "low": 1.0,
    "medium": 2.0,
    "high": 3.0,
    "ignored": 1.0,
    "liked": 2.0,
    "commented": 3.0,
    "shared": 4.0,
}


def _safe_float(value: Any, digits: int = 4) -> float:
    return round(float(value), digits)


def _load_df() -> pd.DataFrame:
    df = pd.read_csv(_DATA_PATH)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["time"] = pd.to_datetime(df["time"], format="%H:%M:%S", errors="coerce")
    df["hour"] = df["time"].dt.hour
    df["month"] = df["date"].dt.to_period("M").astype(str)
    df["day_name"] = df["date"].dt.day_name()
    df["gender_normalized"] = df["gender"].astype(str).str.strip().str.lower()
    df["age_group_normalized"] = df["age_group"].astype(str).str.strip()
    df["engagement_score"] = (
        df["engagement_level"].astype(str).str.strip().str.lower().map(_ENGAGEMENT_SCORE).fillna(2.0)
    )
    return df


def _kpis(df: pd.DataFrame) -> list[dict[str, Any]]:
    return [
        {
            "id": "avg_ctr",
            "label": "Avg CTR",
            "value": _safe_float(df["click_through_rate"].mean() * 100, 2),
            "unit": "%",
        },
        {
            "id": "avg_conversion_rate",
            "label": "Avg Conversion Rate",
            "value": _safe_float(df["conversion_rate"].mean() * 100, 2),
            "unit": "%",
        },
        {
            "id": "avg_roi",
            "label": "Avg ROI Score",
            "value": _safe_float(df["ROI"].mean(), 2),
            "unit": "x",
        },
        {
            "id": "avg_view_time",
            "label": "Avg View Time",
            "value": _safe_float(df["view_time"].mean(), 1),
            "unit": "sec",
        },
    ]


def _ad_topic_roi_chart(df: pd.DataFrame) -> dict[str, Any]:
    grouped = (
        df.groupby("ad_topic", as_index=False)["ROI"]
        .mean()
        .sort_values("ROI", ascending=False)
    )
    grouped["ROI"] = grouped["ROI"].round(3)
    return {
        "id": "ad_topic_vs_avg_roi",
        "title": "Ad Topic vs Avg ROI",
        "description": "Average ROI performance by ad topic.",
        "type": "bar",
        "plotly": {
            "data": [
                {
                    "type": "bar",
                    "x": grouped["ad_topic"].tolist(),
                    "y": grouped["ROI"].tolist(),
                    "marker": {"color": "#6366f1"},
                }
            ],
            "layout": {
                "margin": {"l": 40, "r": 16, "t": 26, "b": 60},
                "paper_bgcolor": "rgba(0,0,0,0)",
                "plot_bgcolor": "rgba(0,0,0,0)",
                "yaxis": {"title": "Avg ROI"},
                "xaxis": {"title": "Ad Topic"},
            },
        },
        "chat_context": {
            "aggregation": "mean(ROI) by ad_topic",
            "data_sample": grouped.head(10).to_dict(orient="records"),
        },
    }


def _device_engagement_roi_chart(df: pd.DataFrame) -> dict[str, Any]:
    stack = (
        df.pivot_table(
            index="device_type",
            columns="engagement_level",
            values="user_id",
            aggfunc="count",
            fill_value=0,
        )
        .reset_index()
        .sort_values("device_type")
    )
    roi_by_device = df.groupby("device_type", as_index=False)["ROI"].mean()
    roi_by_device["ROI"] = roi_by_device["ROI"].round(3)

    bars: list[dict[str, Any]] = []
    for level, color in [("low", "#f59e0b"), ("medium", "#06b6d4"), ("high", "#22c55e")]:
        if level in stack.columns:
            bars.append(
                {
                    "type": "bar",
                    "name": f"{level.title()} Engagement",
                    "x": stack["device_type"].tolist(),
                    "y": stack[level].astype(int).tolist(),
                    "marker": {"color": color},
                }
            )

    bars.append(
        {
            "type": "scatter",
            "name": "Avg ROI",
            "x": roi_by_device["device_type"].tolist(),
            "y": roi_by_device["ROI"].tolist(),
            "yaxis": "y2",
            "mode": "lines+markers",
            "line": {"color": "#8b5cf6", "width": 3},
            "marker": {"size": 7},
        }
    )

    return {
        "id": "roi_engagement_by_device",
        "title": "ROI & Engagement by Device",
        "description": "Stacked engagement volume by device with ROI trend overlay.",
        "type": "stacked_bar_with_line",
        "plotly": {
            "data": bars,
            "layout": {
                "barmode": "stack",
                "margin": {"l": 44, "r": 44, "t": 20, "b": 90},
                "paper_bgcolor": "rgba(0,0,0,0)",
                "plot_bgcolor": "rgba(0,0,0,0)",
                "xaxis": {"title": "Device Type"},
                "yaxis": {"title": "Engagement Count"},
                "yaxis2": {"title": "Avg ROI", "overlaying": "y", "side": "right"},
                "legend": {"orientation": "h", "x": 0, "xanchor": "left", "y": -0.35, "yanchor": "top"},
            },
        },
        "chat_context": {
            "aggregation": "count(users) by device_type and engagement_level; mean(ROI) by device_type",
            "data_sample": stack.to_dict(orient="records"),
        },
    }


def _age_gender_roi_heatmap(df: pd.DataFrame) -> dict[str, Any]:
    age_order = ["18-24", "25-34", "35-44", "45-54", "55+"]
    gender_order = ["male", "female"]
    pivot = (
        df.pivot_table(
            index="gender_normalized",
            columns="age_group_normalized",
            values="ROI",
            aggfunc="mean",
        )
        .reindex(index=gender_order, columns=age_order)
    )
    roi_default = float(df["ROI"].mean()) if not df["ROI"].dropna().empty else 0.0
    pivot = pivot.fillna(roi_default).round(2)
    y_labels = [label.title() for label in pivot.index.tolist()]
    x_labels = [str(label) for label in pivot.columns.tolist()]

    return {
        "id": "avg_roi_age_gender_heatmap",
        "title": "AVG ROI BY AGE GROUP & GENDER",
        "description": "Average ROI by age-group and gender segments.",
        "type": "heatmap",
        "plotly": {
            "data": [
                {
                    "type": "heatmap",
                    "x": x_labels,
                    "y": y_labels,
                    "z": pivot.values.tolist(),
                    "colorscale": [
                        [0.0, "#eef3ff"],
                        [0.4, "#cce7ee"],
                        [0.7, "#8cd6cf"],
                        [1.0, "#2fbe7f"],
                    ],
                    "zmin": float(pivot.min().min()),
                    "zmax": float(pivot.max().max()),
                    "xgap": 6,
                    "ygap": 6,
                    "text": pivot.values.tolist(),
                    "texttemplate": "%{text:.2f}",
                    "textfont": {"color": "#0f172a", "size": 10},
                    "hovertemplate": "Gender: %{y}<br>Age Group: %{x}<br>Avg ROI: %{z:.2f}<extra></extra>",
                    "showscale": False,
                }
            ],
            "layout": {
                "margin": {"l": 34, "r": 10, "t": 28, "b": 30},
                "paper_bgcolor": "rgba(0,0,0,0)",
                "plot_bgcolor": "rgba(0,0,0,0)",
                "xaxis": {
                    "title": "",
                    "side": "top",
                    "showgrid": False,
                    "tickfont": {"size": 10, "color": "#64748b"},
                    "ticks": "",
                },
                "yaxis": {"title": "", "showgrid": False, "tickfont": {"size": 11}, "autorange": "reversed"},
            },
        },
        "chat_context": {
            "aggregation": "mean(ROI) by age_group and gender",
            "data_sample": pivot.reset_index().rename(columns={"gender": "Gender"}).to_dict(orient="records"),
        },
    }


def _hourly_engagement_heatmap(df: pd.DataFrame) -> dict[str, Any]:
    hourly = (
        df.groupby("hour", as_index=False)["engagement_score"]
        .mean()
        .dropna(subset=["hour"])
        .sort_values("hour")
    )
    hourly["hour"] = hourly["hour"].astype(int)
    hourly = hourly.set_index("hour").reindex(range(24))
    default_score = (
        float(hourly["engagement_score"].mean()) if hourly["engagement_score"].notna().any() else 2.0
    )
    hourly["engagement_score"] = hourly["engagement_score"].fillna(default_score).round(2)
    hourly = hourly.reset_index().rename(columns={"index": "hour"})

    # Render as compact hour tiles (6 columns x 4 rows) instead of one long strip.
    columns_per_row = 6
    x_labels = list(range(1, columns_per_row + 1))
    row_labels = [f"row_{index}" for index in range(1, 5)]
    hour_text_matrix: list[list[str]] = []
    intensity_matrix: list[list[float]] = []
    for start in range(0, 24, columns_per_row):
        chunk = hourly.iloc[start : start + columns_per_row]
        hour_text_matrix.append([str(int(value)) for value in chunk["hour"].tolist()])
        intensity_matrix.append(chunk["engagement_score"].astype(float).tolist())

    return {
        "id": "hourly_engagement_heatmap",
        "title": "HOURLY ENGAGEMENT HEATMAP (BY HOUR OF DAY)",
        "description": "Hour tiles (color indicates engagement intensity).",
        "type": "heatmap",
        "plotly": {
            "data": [
                {
                    "type": "heatmap",
                    "x": x_labels,
                    "y": row_labels,
                    "z": intensity_matrix,
                    "colorscale": [
                        [0.0, "#ebf3ff"],
                        [0.35, "#c7daf7"],
                        [0.7, "#82ace8"],
                        [1.0, "#3f7fd9"],
                    ],
                    "xgap": 6,
                    "ygap": 6,
                    "text": hour_text_matrix,
                    "texttemplate": "%{text}",
                    "textfont": {"color": "#0f172a", "size": 12},
                    "hovertemplate": "Hour: %{text}<br>Engagement Intensity: %{z:.2f}<extra></extra>",
                    "showscale": False,
                }
            ],
            "layout": {
                "margin": {"l": 8, "r": 8, "t": 28, "b": 12},
                "paper_bgcolor": "rgba(0,0,0,0)",
                "plot_bgcolor": "rgba(0,0,0,0)",
                "xaxis": {
                    "title": "",
                    "showgrid": False,
                    "showticklabels": False,
                    "ticks": "",
                },
                "yaxis": {
                    "title": "",
                    "showgrid": False,
                    "showticklabels": False,
                    "zeroline": False,
                    "fixedrange": True,
                },
            },
        },
        "chat_context": {
            "aggregation": "mean(engagement_score) by hour",
            "data_sample": hourly.to_dict(orient="records"),
        },
    }


def _content_type_roi_share(df: pd.DataFrame) -> dict[str, Any]:
    grouped = (
        df.groupby("content_type", as_index=False)["ROI"]
        .sum()
        .sort_values("ROI", ascending=False)
    )
    grouped["ROI"] = grouped["ROI"].round(3)

    return {
        "id": "content_type_roi_share",
        "title": "Content Type ROI Share",
        "description": "Share of total ROI contributed by each content type.",
        "type": "donut",
        "plotly": {
            "data": [
                {
                    "type": "pie",
                    "labels": grouped["content_type"].tolist(),
                    "values": grouped["ROI"].tolist(),
                    "hole": 0.56,
                    "textinfo": "label+percent",
                }
            ],
            "layout": {
                "margin": {"l": 16, "r": 16, "t": 26, "b": 16},
                "paper_bgcolor": "rgba(0,0,0,0)",
            },
        },
        "chat_context": {
            "aggregation": "sum(ROI) by content_type",
            "data_sample": grouped.to_dict(orient="records"),
        },
    }


def _monthly_volume_performance(df: pd.DataFrame) -> dict[str, Any]:
    grouped = (
        df.groupby("month", as_index=False)
        .agg(
            campaign_volume=("ad_id", "count"),
            avg_roi=("ROI", "mean"),
            avg_ctr=("click_through_rate", "mean"),
            avg_cvr=("conversion_rate", "mean"),
        )
        .sort_values("month")
    )
    grouped["avg_roi"] = grouped["avg_roi"].round(3)
    grouped["avg_ctr"] = (grouped["avg_ctr"] * 100).round(3)
    grouped["avg_cvr"] = (grouped["avg_cvr"] * 100).round(3)

    return {
        "id": "monthly_campaign_volume_with_roi_ctr_cvr",
        "title": "Monthly Campaign Volume + ROI/CTR/CVR",
        "description": "Monthly campaign count with ROI, CTR and CVR trend lines.",
        "type": "combo",
        "plotly": {
            "data": [
                {
                    "type": "bar",
                    "name": "Campaign Volume",
                    "x": grouped["month"].tolist(),
                    "y": grouped["campaign_volume"].astype(int).tolist(),
                    "marker": {
                        "color": "#93c5fd",
                        "line": {"color": "#60a5fa", "width": 0.8},
                    },
                    "opacity": 0.95,
                    "yaxis": "y",
                },
                {
                    "type": "scatter",
                    "name": "Avg ROI",
                    "x": grouped["month"].tolist(),
                    "y": grouped["avg_roi"].tolist(),
                    "mode": "lines",
                    "line": {
                        "color": "#22c55e",
                        "width": 2,
                        "dash": "solid",
                        "shape": "spline",
                        "smoothing": 0.7,
                    },
                    "opacity": 0.9,
                    "yaxis": "y2",
                },
                {
                    "type": "scatter",
                    "name": "Avg CTR %",
                    "x": grouped["month"].tolist(),
                    "y": grouped["avg_ctr"].tolist(),
                    "mode": "lines",
                    "line": {
                        "color": "#8b5cf6",
                        "width": 1.6,
                        "dash": "dash",
                        "shape": "spline",
                        "smoothing": 0.7,
                    },
                    "opacity": 0.85,
                    "yaxis": "y2",
                },
                {
                    "type": "scatter",
                    "name": "Avg CVR %",
                    "x": grouped["month"].tolist(),
                    "y": grouped["avg_cvr"].tolist(),
                    "mode": "lines",
                    "line": {
                        "color": "#14b8a6",
                        "width": 1.6,
                        "dash": "dot",
                        "shape": "spline",
                        "smoothing": 0.7,
                    },
                    "opacity": 0.85,
                    "yaxis": "y2",
                },
            ],
            "layout": {
                "margin": {"l": 52, "r": 58, "t": 58, "b": 58},
                "paper_bgcolor": "rgba(0,0,0,0)",
                "plot_bgcolor": "rgba(0,0,0,0)",
                "xaxis": {
                    "title": {"text": "Month", "font": {"size": 11, "color": "#475569"}},
                    "showgrid": False,
                    "zeroline": False,
                    "tickfont": {"size": 10, "color": "#64748b"},
                },
                "yaxis": {
                    "title": {"text": "Campaign Volume", "font": {"size": 11, "color": "#60a5fa"}},
                    "tickfont": {"size": 10, "color": "#60a5fa"},
                    "showgrid": True,
                    "gridcolor": "#e2e8f0",
                    "gridwidth": 1,
                    "zeroline": False,
                },
                "yaxis2": {
                    "title": {"text": "ROI / Rate (%)", "font": {"size": 11, "color": "#22c55e"}},
                    "tickfont": {"size": 10, "color": "#22c55e"},
                    "overlaying": "y",
                    "side": "right",
                    "showgrid": False,
                    "zeroline": False,
                },
                "legend": {
                    "orientation": "h",
                    "x": 0,
                    "xanchor": "left",
                    "y": 1.16,
                    "yanchor": "bottom",
                    "entrywidth": 110,
                    "entrywidthmode": "pixels",
                    "tracegroupgap": 10,
                },
            },
        },
        "chat_context": {
            "aggregation": "count(ad_id), mean(ROI), mean(CTR), mean(CVR) by month",
            "data_sample": grouped.to_dict(orient="records"),
        },
    }


def build_dashboard_payload() -> dict[str, Any]:
    df = _load_df()
    charts = [
        _ad_topic_roi_chart(df),
        _device_engagement_roi_chart(df),
        _age_gender_roi_heatmap(df),
        _hourly_engagement_heatmap(df),
        _content_type_roi_share(df),
        _monthly_volume_performance(df),
    ]
    return {
        "kpis": _kpis(df),
        "charts": charts,
    }
