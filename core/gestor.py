import time
import queue
from core.sensor import SensorIoT

class GestorSensores:
    """Gestor centralizado para múltiples sensores"""
    
    def __init__(self, modelo_anomalias):
        """
        Inicializa el gestor de sensores
        
        Args:
            modelo_anomalias (ModeloAnomalias): Instancia del modelo de detección
        """
        self.modelo_anomalias = modelo_anomalias
        self.sensores = {}
        self.data_queue_global = queue.Queue()
        self.monitor_thread = None
        self.monitoring = False
    
    def agregar_sensor(self, sensor_id, interval=1.0, buffer_size=100):
        """Agrega un nuevo sensor al sistema"""
        if sensor_id not in self.sensores:
            sensor = SensorIoT(sensor_id, self.modelo_anomalias, interval, buffer_size)
            self.sensores[sensor_id] = sensor
            print(f"➕ Sensor {sensor_id} agregado al sistema")
            return True
        else:
            print(f"⚠ Sensor {sensor_id} ya existe")
            return False
    
    def iniciar_sensor(self, sensor_id):
        """Inicia un sensor específico"""
        if sensor_id in self.sensores:
            return self.sensores[sensor_id].iniciar()
        return False
    
    def detener_sensor(self, sensor_id):
        """Detiene un sensor específico"""
        if sensor_id in self.sensores:
            return self.sensores[sensor_id].detener()
        return False
    
    def iniciar_todos(self):
        """Inicia todos los sensores"""
        for sensor_id in self.sensores:
            self.iniciar_sensor(sensor_id)
        print(f"🚀 {len(self.sensores)} sensores iniciados")
    
    def detener_todos(self):
        """Detiene todos los sensores"""
        for sensor_id in self.sensores:
            self.detener_sensor(sensor_id)
        print(f"⏹ {len(self.sensores)} sensores detenidos")
    
    def obtener_estado_general(self):
        """Obtiene el estado de todos los sensores"""
        estados = {}
        for sensor_id, sensor in self.sensores.items():
            estados[sensor_id] = sensor.obtener_estado()
        return estados
    
    def mostrar_alertas_tiempo_real(self, duracion_segundos=30):
        """Monitorea y muestra alertas en tiempo real"""
        print(f"🔍 Monitoreando alertas por {duracion_segundos} segundos...")
        inicio = time.time()
        ultima_actualizacion_estado = 0
        
        while time.time() - inicio < duracion_segundos:
            tiempo_actual = time.time()
            
            # Revisar alertas de cada sensor
            for sensor_id, sensor in self.sensores.items():
                if not sensor.data_queue.empty():
                    try:
                        lectura = sensor.data_queue.get_nowait()
                        
                        if lectura['alerta_total']:
                            timestamp = lectura['timestamp'].strftime('%H:%M:%S')
                            print(f"\n🚨 ALERTA [{sensor_id}] - {timestamp}")
                            print(f"   📊 T: {lectura['temperatura_c']:.1f}°C | "
                                  f"V: {lectura['voltaje_v']:.1f}V | "
                                  f"E: {lectura['eficiencia_pct']:.1f}%")
                            print(f"   🎯 Fuentes: {', '.join(lectura['fuente_alerta'])}")
                            
                            if lectura['delta_efic'] is not None:
                                print(f"   📉 Δ Eficiencia: {lectura['delta_efic']:.2f}%")
                    
                    except queue.Empty:
                        pass
            
            # Mostrar estado cada 10 segundos
            if tiempo_actual - ultima_actualizacion_estado >= 10:
                print(f"\n📈 Estado del Sistema ({int(tiempo_actual - inicio)}s)")
                estados = self.obtener_estado_general()
                for sensor_id, estado in estados.items():
                    print(f"   [{sensor_id}]: {estado['total_lecturas']} lecturas, "
                          f"{estado['total_anomalias']} anomalías "
                          f"({estado['tasa_anomalias_pct']:.1f}%)")
                ultima_actualizacion_estado = tiempo_actual
            
            time.sleep(0.1)

