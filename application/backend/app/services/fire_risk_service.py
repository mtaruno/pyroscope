"""
Fire Risk Calculation Service
Calculates fire risk based on temperature, humidity, and fuel load
"""
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class FireRiskService:
    """Service for calculating fire risk from environmental and fuel data"""
    
    # Weights for fire risk calculation
    TEMP_WEIGHT = 0.3
    HUMIDITY_WEIGHT = 0.2
    FUEL_WEIGHT = 0.5
    
    # Reference values for normalization
    MAX_TEMP = 50.0  # °C
    MAX_FUEL = 2.0   # tons/acre (total combined fuel)
    
    @classmethod
    def calculate_fire_risk(
        cls,
        plant_temperature: Optional[float] = None,
        air_humidity: Optional[float] = None,
        one_hour_fuel: Optional[float] = None,
        ten_hour_fuel: Optional[float] = None,
        hundred_hour_fuel: Optional[float] = None
    ) -> float:
        """
        Calculate fire risk score (0-1 range)
        
        Formula:
        - Temperature factor: 30% (higher temp = higher risk)
        - Humidity factor: 20% (lower humidity = higher risk)
        - Fuel factor: 50% (more fuel = higher risk)
        
        Args:
            plant_temperature: Ground/plant temperature in °C
            air_humidity: Air humidity in %
            one_hour_fuel: 1-hour fuel load in tons/acre
            ten_hour_fuel: 10-hour fuel load in tons/acre
            hundred_hour_fuel: 100-hour fuel load in tons/acre
            
        Returns:
            Fire risk score between 0 (low) and 1 (high)
        """
        risk_components = []
        
        # Temperature factor (0-1)
        if plant_temperature is not None:
            temp_factor = min(plant_temperature / cls.MAX_TEMP, 1.0) * cls.TEMP_WEIGHT
            risk_components.append(temp_factor)
        
        # Humidity factor (0-1) - inverted: lower humidity = higher risk
        if air_humidity is not None:
            humidity_factor = ((100 - air_humidity) / 100) * cls.HUMIDITY_WEIGHT
            risk_components.append(humidity_factor)
        
        # Fuel factor (0-1)
        if any([one_hour_fuel, ten_hour_fuel, hundred_hour_fuel]):
            total_fuel = (
                (one_hour_fuel or 0) +
                (ten_hour_fuel or 0) +
                (hundred_hour_fuel or 0)
            )
            fuel_factor = min(total_fuel / cls.MAX_FUEL, 1.0) * cls.FUEL_WEIGHT
            risk_components.append(fuel_factor)
        
        # If no data available, return None
        if not risk_components:
            return None
        
        # Calculate final risk score
        fire_risk = sum(risk_components)
        
        # Ensure it's within 0-1 range
        fire_risk = max(0.0, min(1.0, fire_risk))
        
        return round(fire_risk, 4)
    
    @classmethod
    def get_risk_level(cls, fire_risk: float) -> str:
        """
        Convert numeric fire risk to categorical level
        
        Args:
            fire_risk: Fire risk score (0-1)
            
        Returns:
            Risk level: 'low', 'medium', or 'high'
        """
        if fire_risk < 0.33:
            return 'low'
        elif fire_risk < 0.67:
            return 'medium'
        else:
            return 'high'
    
    @classmethod
    def calculate_batch_risk(cls, data_points: list) -> list:
        """
        Calculate fire risk for multiple data points
        
        Args:
            data_points: List of environmental data records
            
        Returns:
            List of dictionaries with fire_risk added
        """
        results = []
        
        for point in data_points:
            fire_risk = cls.calculate_fire_risk(
                plant_temperature=point.plant_temperature,
                air_humidity=point.air_humidity,
                one_hour_fuel=getattr(point, 'one_hour_fuel', None),
                ten_hour_fuel=getattr(point, 'ten_hour_fuel', None),
                hundred_hour_fuel=getattr(point, 'hundred_hour_fuel', None)
            )
            
            results.append({
                'point': point,
                'fire_risk': fire_risk
            })
        
        return results
