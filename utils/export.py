import io
import pandas as pd


def clean_excel_datetimes(df):
    export_df = df.copy()

    for col in export_df.columns:
        if pd.api.types.is_datetime64_any_dtype(export_df[col]):
            try:
                export_df[col] = export_df[col].dt.tz_localize(None)
            except TypeError:
                pass

    return export_df


def dataframe_to_excel_bytes(df):
    output = io.BytesIO()

    export_df = clean_excel_datetimes(df)

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        export_df.to_excel(writer, index=False, sheet_name="JSM Data")

    return output.getvalue()