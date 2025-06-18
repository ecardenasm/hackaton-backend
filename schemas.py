from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime

class LecturaSensorDTO(BaseModel):
    timestamp: datetime
    sensor_id: str
    temperatura_c: float
    voltaje_v: float
    eficiencia_pct: float
    alerta_total: bool
    fuentes_alerta: List[str]
    delta_eficiencia: Optional[float]
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class EstadoSensorDTO(BaseModel):
    sensor_id: str
    activo: bool
    total_lecturas: int
    total_anomalias: int
    tasa_anomalias_pct: float
    lecturas_por_minuto: int
    tiene_alerta_activa: bool
    ultima_lectura: Optional[LecturaSensorDTO]

class SistemaDTO(BaseModel):
    sensores: Dict[str, EstadoSensorDTO]
    total_lecturas: int
    total_anomalias: int
    tasa_global_anomalias: float
