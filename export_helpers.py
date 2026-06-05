"""Asset export helpers for dataframe to CSV/Excel conversion."""
import io
import json
import logging
from typing import Optional
from datetime import datetime
import pandas as pd

logger = logging.getLogger(__name__)


def export_profiles_to_csv(df: pd.DataFrame) -> bytes:
    """Export profile dataframe to CSV format.

    Args:
        df: Raw profile dataframe from db

    Returns:
        CSV bytes ready for download
    """
    if df.empty:
        return b""

    # Use prepared display dataframe
    from ui_helpers import prepare_profiles_dataframe

    df_display = prepare_profiles_dataframe(df)

    # Convert to CSV with UTF-8 encoding
    csv_buffer = io.StringIO()
    df_display.to_csv(csv_buffer, index=False, encoding="utf-8")
    return csv_buffer.getvalue().encode("utf-8")


def export_profiles_to_excel(df: pd.DataFrame) -> bytes:
    """Export profile dataframe to Excel (XLSX) format.

    Args:
        df: Raw profile dataframe from db

    Returns:
        Excel bytes ready for download
    """
    if df.empty:
        return b""

    # Use prepared display dataframe
    from ui_helpers import prepare_profiles_dataframe

    df_display = prepare_profiles_dataframe(df)

    # Create BytesIO buffer
    excel_buffer = io.BytesIO()

    # Write to Excel with basic formatting
    try:
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            df_display.to_excel(
                writer,
                sheet_name="Profiles",
                index=False,
                freeze_panes=(1, 0),
            )

            # Auto-adjust column widths
            worksheet = writer.sheets["Profiles"]
            for idx, col in enumerate(df_display.columns, 1):
                max_length = max(
                    df_display[col].astype(str).str.len().max(),
                    len(col),
                )
                max_length = min(max_length + 2, 50)
                col_letter = chr(64 + idx)
                worksheet.column_dimensions[col_letter].width = max_length

        excel_buffer.seek(0)
        return excel_buffer.getvalue()

    except ImportError:
        logger.error("openpyxl not installed. Install with: pip install openpyxl")
        return b""
    except Exception as e:
        logger.error(f"Failed to generate Excel: {e}")
        return b""


def generate_export_filename(extension: str) -> str:
    """Generate timestamped export filename."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"linkedin_profiles_export_{timestamp}.{extension}"
