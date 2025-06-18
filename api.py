from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from core.modelo import ModeloAnomalias
from core.gestor import GestorSensores
from schemas import SistemaDTO, EstadoSensorDTO, LecturaSensorDTO
import asyncio
import json

app = FastAPI()

# Inicializar el sistema existente
modelo = ModeloAnomalias()
gestor = GestorSensores(modelo)

# Configurar sensores (esto podría ir en un startup event)
gestor.agregar_sensor("SENSOR_01", interval=0.8, buffer_size=150)
gestor.agregar_sensor("SENSOR_02", interval=1.2, buffer_size=150)
gestor.agregar_sensor("SENSOR_03", interval=1.0, buffer_size=150)
gestor.iniciar_todos()

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

@app.get("/api/sistema", response_model=SistemaDTO)
async def estado_sistema():
    estados = gestor.obtener_estado_general()
    total_lecturas = sum(e['total_lecturas'] for e in estados.values())
    total_anomalias = sum(e['total_anomalias'] for e in estados.values())
    
    return {
        "sensores": estados,
        "total_lecturas": total_lecturas,
        "total_anomalias": total_anomalias,
        "tasa_global_anomalias": (total_anomalias/total_lecturas)*100 if total_lecturas > 0 else 0
    }

@app.get("/api/sensores/{sensor_id}/lecturas", response_model=List[LecturaSensorDTO])
async def obtener_lecturas(sensor_id: str, limit: int = 10):
    sensor = gestor.sensores.get(sensor_id)
    if sensor:
        return sensor.obtener_ultimas_lecturas(limit)
    return []

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Enviar actualizaciones cada segundo
            estados = gestor.obtener_estado_general()
            sistema_dto = SistemaDTO(
                sensores=estados,
                total_lecturas=sum(e['total_lecturas'] for e in estados.values()),
                total_anomalias=sum(e['total_anomalias'] for e in estados.values()),
                tasa_global_anomalias=sum(e['total_anomalias'] for e in estados.values())/sum(e['total_lecturas'] for e in estados.values()) if sum(e['total_lecturas'] for e in estados.values()) > 0 else 0
            )
            await websocket.send_json(sistema_dto.dict())
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.on_event("shutdown")
def shutdown_event():
    gestor.detener_todos()
