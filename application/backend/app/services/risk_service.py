from typing import Optional


class RiskService:
    @staticmethod
    def calculate_risk_level(
        avg_plant_temp: Optional[float],
        avg_air_temp: Optional[float],
        avg_humidity: Optional[float],
        fuel_load: Optional[str]
    ) -> str:
        """
        Calculate risk level based on environmental data.
        This is a simplified algorithm and should be replaced with
        actual wildfire risk assessment logic.
        """
        risk_score = 0
        
        # Temperature factor
        if avg_plant_temp and avg_plant_temp > 32:
            risk_score += 2
        elif avg_plant_temp and avg_plant_temp > 28:
            risk_score += 1
        
        # Humidity factor (lower humidity = higher risk)
        if avg_humidity and avg_humidity < 40:
            risk_score += 2
        elif avg_humidity and avg_humidity < 60:
            risk_score += 1
        
        # Fuel load factor
        if fuel_load:
            fuel_lower = fuel_load.lower()
            if fuel_lower == "high":
                risk_score += 2
            elif fuel_lower == "medium":
                risk_score += 1
        
        # Determine risk level
        if risk_score >= 4:
            return "high"
        elif risk_score >= 2:
            return "medium"
        else:
            return "low"
