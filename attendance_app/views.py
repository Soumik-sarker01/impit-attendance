import os

import pandas as pd
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render
from pandas.tseries.offsets import Day


def upload_file(request):
    if request.method == "POST":
        excel_file = request.FILES.get("excel_file", None)
        selected_date = request.POST.get("selected_date", None)  # Capture selected date

        if not excel_file:
            return HttpResponse("No file uploaded.")

        file_extension = os.path.splitext(excel_file.name)[1]
        if file_extension.lower() != ".xlsx":
            return HttpResponse("Error: Please upload an '.xlsx' file.")

        try:
            entries_df = pd.read_excel(excel_file, engine="openpyxl")
            entries_df = entries_df[["Name", "Date/Time"]]
            preloaded_file_path = os.path.join(settings.BASE_DIR, "Shifts.xlsx")
            shifts_df = pd.read_excel(preloaded_file_path, engine="openpyxl")

            entries_df["Date/Time"] = pd.to_datetime(entries_df["Date/Time"])
            merged_df = entries_df.merge(shifts_df, how="left", on=["Name"])

            if merged_df["No."].notnull().all():
                merged_df["No."] = merged_df["No."].astype(int)

            if selected_date:
                merged_df = merged_df[
                    merged_df["Date/Time"].dt.strftime("%Y-%m-%d") == selected_date
                ]

            shifts = ["Day", "Night"]
            all_shift_reports = []

            for shift in shifts:
                shift_df = merged_df[merged_df["Shift"] == shift]
                start_date = shift_df["Date/Time"].min().date()
                end_date = shift_df["Date/Time"].max().date()
                all_dates = pd.date_range(start=start_date, end=end_date, freq="D")

                employee_info = {}
                for _, row in shift_df.iterrows():
                    employee_info[row["Name"]] = {
                        "Department": row["Department"],
                        "No.": int(row["No."]) if pd.notnull(row["No."]) else None,
                    }

                grouped_data = {}
                for date in all_dates:
                    weekday = date.dayofweek
                    date_str = date.strftime("%Y-%m-%d (%A)")

                    for name in shift_df["Name"].unique():
                        if name not in grouped_data:
                            grouped_data[name] = {}

                        department = employee_info[name]["Department"]
                        id = employee_info[name]["No."]
                        if date_str not in grouped_data[name]:
                            grouped_data[name][date_str] = {
                                "Department": department,
                                "ID": id,
                                "Employee Name": name,
                                "Date": date_str,
                                "First Entry": "-",
                                "Last Exit": "-",
                                "Duration": "-",
                                "Present": "-",
                                "Absent": "Yes",
                                "Late": "-",
                            }
                        # Custom late time logic per department or employee
                        if department == "AyNaur":
                            late_time = "12:00:00"
                        elif department == "Shibori":
                            late_time = "09:00:00"
                        elif name in ["Joe", "Austin"]:
                            late_time = "10:00:00"
                        elif name == "Mark":
                            late_time = "20:00:00"
                        elif name in [
                            "Morgan",
                            "Samuel",
                            "Andrew",
                            "George",
                        ]:
                            late_time = "09:00:00"
                        else:
                            late_time = "08:00:00" if shift == "Day" else "19:00:00"

                        if shift == "Night":
                            evening_date = date + Day()
                            morning_entries = shift_df[
                                (shift_df["Name"] == name)
                                & (shift_df["Date/Time"].dt.date == evening_date.date())
                                & (
                                    shift_df["Date/Time"].dt.time
                                    < pd.Timestamp("07:00:00").time()
                                )
                            ]
                            evening_entries = shift_df[
                                (shift_df["Name"] == name)
                                & (shift_df["Date/Time"].dt.date == date.date())
                                & (
                                    shift_df["Date/Time"].dt.time
                                    >= pd.Timestamp("18:00:00").time()
                                )
                            ]
                            date_data = pd.concat(
                                [evening_entries, morning_entries]
                            ).sort_values("Date/Time")
                        else:
                            date_data = shift_df[
                                (shift_df["Name"] == name)
                                & (shift_df["Date/Time"].dt.date == date.date())
                            ]

                        if not date_data.empty:
                            first_entry_time = date_data["Date/Time"].iloc[0]
                            last_exit_time = date_data["Date/Time"].iloc[-1]

                            # Convert late_time string to a datetime.time object for comparison
                            late_time_obj = pd.to_datetime(late_time).time()

                            # Check if the first entry is later than the late_time
                            is_late = (
                                "Yes"
                                if first_entry_time.time() > late_time_obj
                                else "No"
                            )

                            # Calculate duration as a timedelta object
                            duration = last_exit_time - first_entry_time
                            hours, remainder = divmod(duration.seconds, 3600)
                            minutes, seconds = divmod(remainder, 60)
                            formatted_duration = f"{hours}h {minutes}m"

                            grouped_data[name][date_str].update(
                                {
                                    "First Entry": first_entry_time.strftime(
                                        "%I:%M %p"
                                    ),
                                    "Last Exit": last_exit_time.strftime("%I:%M %p"),
                                    "Duration": formatted_duration,
                                    "Present": "Yes",
                                    "Absent": "No",
                                    "Late": is_late,
                                }
                            )
                        elif weekday in [5, 6]:  # Handling weekends
                            grouped_data[name][date_str].update(
                                {
                                    "Present": "Weekend",
                                    "Absent": "Weekend",
                                    "Late": "Weekend",
                                }
                            )

                output_data = []
                for name, dates in sorted(grouped_data.items()):
                    for date, record in sorted(dates.items()):
                        output_data.append(record)

                shift_report_df = pd.DataFrame(output_data)
                all_shift_reports.append((shift, shift_report_df.to_dict("records")))

            unique_departments = sorted(shifts_df["Department"].unique().tolist())
            unique_names = sorted(merged_df["Name"].unique().tolist())

            return render(
                request,
                "display_data.html",
                {
                    "shift_reports": all_shift_reports,
                    "departments": unique_departments,
                    "employee_names": unique_names,
                },
            )

        except Exception as e:
            return HttpResponse(f"An error occurred: {e}")

    else:
        return render(request, "upload.html")
