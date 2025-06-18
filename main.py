# main.py
from core.modelo import ModeloAnomalias
from core.sensor import SensorIoT
from core.gestor import GestorSensores
import time

if __name__ == "__main__":
    print("🔧 Inicializando Sistema Modular")

    modelo = ModeloAnomalias()

    gestor = GestorSensores(modelo)
    gestor.agregar_sensor("SENSOR_01", interval=0.8)
    gestor.agregar_sensor("SENSOR_02", interval=1.2)
    gestor.agregar_sensor("SENSOR_03", interval=1.0)

    try:
        gestor.iniciar_todos()
        gestor.mostrar_alertas_tiempo_real(duracion_segundos=30)
    except KeyboardInterrupt:
        print("⏹ Interrumpido por usuario")
    finally:
        gestor.detener_todos()
        print("✅ Sistema finalizado")

