from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.environmental import EnvironmentalData
from app.models.scan import ScanRecord
from app.models.waypoint_sample import ScanWaypointSample


def _round_or_none(value: Optional[float], digits: int) -> Optional[float]:
    if value is None:
        return None
    return round(float(value), digits)


class ScanAggregateService:
    @staticmethod
    def refresh_scan_aggregates(db: Session, scan_id: int, *, commit: bool = True) -> Optional[ScanRecord]:
        """
        Refresh parent scan aggregate fields from child sample rows.

        Preference order:
        1. `environmental_data` when present, because it has the richer legacy schema.
        2. `scan_waypoint_samples` for live robot captures.
        """
        scan = db.query(ScanRecord).filter(ScanRecord.id == scan_id).first()
        if not scan:
            return None

        env_count, env_plant, env_air, env_humidity = (
            db.query(
                func.count(EnvironmentalData.id),
                func.avg(EnvironmentalData.plant_temperature),
                func.avg(EnvironmentalData.air_temperature),
                func.avg(EnvironmentalData.air_humidity),
            )
            .filter(EnvironmentalData.scan_id == scan_id)
            .one()
        )

        if int(env_count or 0) > 0:
            avg_plant_temp = env_plant
            avg_air_temp = env_air
            avg_humidity = env_humidity
        else:
            _, waypoint_air, waypoint_humidity, waypoint_thermal = (
                db.query(
                    func.count(ScanWaypointSample.id),
                    func.avg(ScanWaypointSample.air_temperature),
                    func.avg(ScanWaypointSample.air_humidity),
                    func.avg(ScanWaypointSample.thermal_mean),
                )
                .filter(ScanWaypointSample.scan_id == scan_id)
                .one()
            )
            avg_plant_temp = waypoint_thermal
            avg_air_temp = waypoint_air
            avg_humidity = waypoint_humidity

        scan.avg_plant_temp = _round_or_none(avg_plant_temp, 2)
        scan.avg_air_temp = _round_or_none(avg_air_temp, 2)
        scan.avg_humidity = _round_or_none(avg_humidity, 2)
        if avg_plant_temp is not None and avg_air_temp is not None:
            scan.temp_diff = round(float(avg_plant_temp) - float(avg_air_temp), 2)
        else:
            scan.temp_diff = None

        if commit:
            db.commit()
            db.refresh(scan)

        return scan
