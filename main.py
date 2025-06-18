import joblib
import numpy as np
import pandas as pd
import threading
import time
from datetime import datetime, timedelta
from collections import deque
import queue
import warnings
from sklearn.exceptions import InconsistentVersionWarning
import json

# Suprimir warnings de versión
warnings.filterwarnings("ignore", category=InconsistentVersionWarning)

class ModeloAnomalias:
    """Clase para manejar el modelo de detección de anomalías"""
    
    def __init__(self, scaler_path="scaler_datos.pkl", modelo_path="modelo_isolation_forest.pkl"):
        """
        Inicializa el modelo de anomalías
        
        Args:
            scaler_path (str): Ruta al archivo del scaler
            modelo_path (str): Ruta al archivo del modelo
        """
        self.scaler_path = scaler_path
        self.modelo_path = modelo_path
        self.scaler = None
        self.modelo = None
        self.modelo_cargado = False
        
        self._cargar_modelos()
    
    def _cargar_modelos(self):
        """Carga los modelos desde archivos"""
        try:
            self.scaler = joblib.load(self.scaler_path)
            self.modelo = joblib.load(self.modelo_path)
            self.modelo_cargado = True
            print(f"✅ Modelos cargados exitosamente")
        except Exception as e:
            print(f"❌ Error cargando modelos: {e}")
            print("⚠ Funcionará sin modelo ML, solo con reglas manuales")
    
    def verificar_estado_completo(self, temp, volt, efic, efic_ant=None):
        """
        Función principal de detección de anomalías
        Adaptada de tu código original
        """
        alerta_modelo = 0
        
        # Predicción con Isolation Forest si está disponible
        if self.modelo_cargado:
            try:
                df = pd.DataFrame([[temp, volt, efic]],
                                columns=['Temperatura_C','Voltaje_V','Eficiencia_%'])
                entrada_scaled = self.scaler.transform(df)
                pred = self.modelo.predict(entrada_scaled)
                alerta_modelo = int(pred[0] == -1)
            except Exception as e:
                print(f"⚠ Error en predicción ML: {e}")
                alerta_modelo = 0
        
        # Reglas manuales
        alerta_voltaje = int(volt < 210)
        alerta_temp = int(temp > 80)
        alerta_eficiencia = 0
        delta_efic = None
        
        if efic_ant is not None:
            delta_efic = efic - efic_ant
            alerta_eficiencia = int(delta_efic < -2.0)
        
        # Alerta total
        alerta_total = bool(alerta_modelo or alerta_voltaje or alerta_temp or alerta_eficiencia)
        
        # Identificar fuentes de alerta
        fuentes = []
        if alerta_modelo:      fuentes.append("Modelo_ML")
        if alerta_voltaje:     fuentes.append("Bajo_Voltaje")
        if alerta_temp:        fuentes.append("Alta_Temperatura")
        if alerta_eficiencia:  fuentes.append("Caida_Eficiencia")
        if not fuentes:        fuentes = ["Normal"]
        
        return {
            "alerta_total": alerta_total,
            "fuente_alerta": fuentes,
            "delta_efic": delta_efic,
            "alertas_individuales": {
                "modelo_ml": bool(alerta_modelo),
                "bajo_voltaje": bool(alerta_voltaje),
                "alta_temperatura": bool(alerta_temp),
                "caida_eficiencia": bool(alerta_eficiencia)
            }
        }


class SensorIoT:
    """Clase para simular un sensor IoT individual"""
    
    def __init__(self, sensor_id, modelo_anomalias, interval=1.0, buffer_size=100):
        """
        Inicializa un sensor IoT
        
        Args:
            sensor_id (str): Identificador único del sensor
            modelo_anomalias (ModeloAnomalias): Instancia del modelo de detección
            interval (float): Intervalo entre lecturas (segundos)
            buffer_size (int): Tamaño del buffer histórico
        """
        self.sensor_id = sensor_id
        self.modelo_anomalias = modelo_anomalias
        self.interval = interval
        self.buffer_size = buffer_size
        
        # Buffer para datos históricos
        self.data_buffer = deque(maxlen=buffer_size)
        
        # Cola thread-safe para comunicación
        self.data_queue = queue.Queue()
        
        # Control de threading
        self.running = False
        self.thread = None
        
        # Estadísticas
        self.total_lecturas = 0
        self.total_anomalias = 0
        self.lecturas_por_minuto = 0
        self.ultima_lectura = None
        
        # Configuración del sensor (simulación)
        self._configurar_sensor()
    
    def _configurar_sensor(self):
        """Configura los parámetros específicos del sensor"""
        # Parámetros base diferenciados por sensor
        sensor_configs = {
            "SENSOR_01": {
                "temp_base": 70.0, "temp_std": 3.0,
                "volt_base": 220.0, "volt_std": 5.0,
                "efic_base": 82.0, "efic_std": 3.0
            },
            "SENSOR_02": {
                "temp_base": 68.0, "temp_std": 2.5,
                "volt_base": 218.0, "volt_std": 4.0,
                "efic_base": 80.0, "efic_std": 2.8
            },
            "SENSOR_03": {
                "temp_base": 72.0, "temp_std": 3.5,
                "volt_base": 222.0, "volt_std": 6.0,
                "efic_base": 84.0, "efic_std": 3.2
            }
        }
        
        config = sensor_configs.get(self.sensor_id, sensor_configs["SENSOR_01"])
        
        self.temp_base = config["temp_base"]
        self.temp_std = config["temp_std"]
        self.volt_base = config["volt_base"]
        self.volt_std = config["volt_std"]
        self.efic_base = config["efic_base"]
        self.efic_std = config["efic_std"]
        
        # Factores de deriva temporal
        self.temp_drift = 0.0
        self.volt_drift = 0.0
        self.efic_drift = 0.0
        
        # Simulación de fallos ocasionales
        self.fallo_probabilidad = 0.02  # 2% de probabilidad de fallo por lectura
    
    def _generar_lectura_sensor(self):
        """Genera una lectura realista del sensor"""
        timestamp = datetime.now()
        
        # Simulación de condiciones normales vs anómalas
        if np.random.random() < self.fallo_probabilidad:
            # Simular condición anómala
            if np.random.random() < 0.3:  # Fallo de voltaje
                voltaje = np.random.normal(200, 5)
            elif np.random.random() < 0.3:  # Sobrecalentamiento
                temperatura = np.random.normal(85, 2)
                voltaje = np.random.normal(self.volt_base + self.volt_drift, self.volt_std)
            else:  # Caída de eficiencia
                temperatura = np.random.normal(self.temp_base + self.temp_drift, self.temp_std)
                voltaje = np.random.normal(self.volt_base + self.volt_drift, self.volt_std)
        else:
            # Condiciones normales
            temperatura = np.random.normal(self.temp_base + self.temp_drift, self.temp_std)
            voltaje = np.random.normal(self.volt_base + self.volt_drift, self.volt_std)
        
        # Eficiencia siempre con su lógica normal
        eficiencia = np.random.normal(self.efic_base + self.efic_drift, self.efic_std)
        
        # Aplicar deriva temporal pequeña
        self.temp_drift += np.random.normal(0, 0.02)
        self.volt_drift += np.random.normal(0, 0.1)
        self.efic_drift += np.random.normal(0, 0.05)
        
        # Limitar derivas extremas
        self.temp_drift = np.clip(self.temp_drift, -3, 3)
        self.volt_drift = np.clip(self.volt_drift, -8, 8)
        self.efic_drift = np.clip(self.efic_drift, -4, 4)
        
        return {
            'timestamp': timestamp,
            'sensor_id': self.sensor_id,
            'temperatura_c': round(temperatura, 2),
            'voltaje_v': round(voltaje, 2),
            'eficiencia_pct': round(eficiencia, 2)
        }
    
    def _procesar_lectura(self, lectura):
        """Procesa una lectura con el modelo de anomalías"""
        # Obtener eficiencia anterior si existe
        efic_anterior = None
        if self.data_buffer:
            efic_anterior = self.data_buffer[-1]['eficiencia_pct']
        
        # Verificar anomalías usando el modelo
        resultado_anomalia = self.modelo_anomalias.verificar_estado_completo(
            lectura['temperatura_c'],
            lectura['voltaje_v'],
            lectura['eficiencia_pct'],
            efic_anterior
        )
        
        # Combinar datos de lectura con resultado de anomalía
        lectura.update(resultado_anomalia)
        
        return lectura
    
    def _loop_sensor(self):
        """Loop principal del sensor ejecutado en thread separado"""
        print(f"🚀 [{self.sensor_id}] Iniciado - Intervalo: {self.interval}s")
        
        contador_lecturas_minuto = 0
        inicio_minuto = time.time()
        
        while self.running:
            try:
                # Generar lectura
                lectura = self._generar_lectura_sensor()
                
                # Procesar con modelo de anomalías
                lectura_procesada = self._procesar_lectura(lectura)
                
                # Almacenar en buffer
                self.data_buffer.append(lectura_procesada)
                
                # Enviar a cola para procesamiento externo
                self.data_queue.put(lectura_procesada.copy())
                
                # Actualizar estadísticas
                self.total_lecturas += 1
                self.ultima_lectura = lectura_procesada
                contador_lecturas_minuto += 1
                
                if lectura_procesada['alerta_total']:
                    self.total_anomalias += 1
                
                # Calcular lecturas por minuto
                if time.time() - inicio_minuto >= 60:
                    self.lecturas_por_minuto = contador_lecturas_minuto
                    contador_lecturas_minuto = 0
                    inicio_minuto = time.time()
                
                # Pausa según intervalo configurado
                time.sleep(self.interval)
                
            except Exception as e:
                print(f"❌ [{self.sensor_id}] Error: {e}")
                time.sleep(self.interval)
    
    def iniciar(self):
        """Inicia el sensor en un thread separado"""
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._loop_sensor)
            self.thread.daemon = True
            self.thread.start()
            return True
        return False
    
    def detener(self):
        """Detiene el sensor"""
        if self.running:
            self.running = False
            if self.thread and self.thread.is_alive():
                self.thread.join(timeout=2)
            return True
        return False
    
    def obtener_estado(self):
        """Obtiene el estado actual del sensor"""
        tasa_anomalias = (self.total_anomalias / max(1, self.total_lecturas)) * 100
        
        return {
            'sensor_id': self.sensor_id,
            'activo': self.running,
            'total_lecturas': self.total_lecturas,
            'total_anomalias': self.total_anomalias,
            'tasa_anomalias_pct': round(tasa_anomalias, 2),
            'lecturas_por_minuto': self.lecturas_por_minuto,
            'buffer_size': len(self.data_buffer),
            'ultima_lectura': self.ultima_lectura['timestamp'].strftime('%H:%M:%S') if self.ultima_lectura else None,
            'tiene_alerta_activa': self.ultima_lectura['alerta_total'] if self.ultima_lectura else False
        }
    
    def obtener_ultimas_lecturas(self, cantidad=10):
        """Obtiene las últimas N lecturas del buffer"""
        if cantidad == 1:
            return list(self.data_buffer)[-1] if self.data_buffer else None
        return list(self.data_buffer)[-cantidad:] if len(self.data_buffer) >= cantidad else list(self.data_buffer)
    
    def obtener_datos_historicos(self):
        """Convierte el buffer a DataFrame para análisis"""
        if not self.data_buffer:
            return pd.DataFrame()
        
        datos = []
        for lectura in self.data_buffer:
            fila = {
                'timestamp': lectura['timestamp'],
                'sensor_id': lectura['sensor_id'],
                'temperatura_c': lectura['temperatura_c'],
                'voltaje_v': lectura['voltaje_v'],
                'eficiencia_pct': lectura['eficiencia_pct'],
                'alerta_total': lectura['alerta_total'],
                'fuentes_alerta': ','.join(lectura['fuente_alerta']),
                'delta_eficiencia': lectura['delta_efic']
            }
            
            # Agregar alertas individuales
            for alerta, activa in lectura['alertas_individuales'].items():
                fila[f'alerta_{alerta}'] = activa
            
            datos.append(fila)
        
        return pd.DataFrame(datos)


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


# Ejemplo de uso del sistema completo
if __name__ == "__main__":
    print("🔧 Inicializando Sistema de Sensores IoT con Isolation Forest")
    
    # 1. Cargar modelo de anomalías
    modelo = ModeloAnomalias()  # Asume que los archivos .pkl están disponibles
    
    # 2. Crear gestor de sensores
    gestor = GestorSensores(modelo)
    
    # 3. Agregar sensores al sistema
    gestor.agregar_sensor("SENSOR_01", interval=0.8, buffer_size=150)
    gestor.agregar_sensor("SENSOR_02", interval=1.2, buffer_size=150)
    gestor.agregar_sensor("SENSOR_03", interval=1.0, buffer_size=150)
    
    
    try:
        # 4. Iniciar todos los sensores
        gestor.iniciar_todos()
        
        # 5. Monitorear en tiempo real
        gestor.mostrar_alertas_tiempo_real(duracion_segundos=30)
        
    except KeyboardInterrupt:
        print("\n⏹ Interrumpido por usuario")
    
    finally:
        # 6. Detener todos los sensores
        gestor.detener_todos()
        
        # 7. Mostrar resumen final
        print(f"\n📊 RESUMEN FINAL DEL SISTEMA")
        print("=" * 50)
        estados_finales = gestor.obtener_estado_general()
        
        total_lecturas = sum(estado['total_lecturas'] for estado in estados_finales.values())
        total_anomalias = sum(estado['total_anomalias'] for estado in estados_finales.values())
        
        for sensor_id, estado in estados_finales.items():
            print(f"\n🔹 {sensor_id}:")
            print(f"   Lecturas totales: {estado['total_lecturas']}")
            print(f"   Anomalías detectadas: {estado['total_anomalias']}")
            print(f"   Tasa de anomalías: {estado['tasa_anomalias_pct']:.2f}%")
            print(f"   Buffer utilizado: {estado['buffer_size']}/150")
        
        print(f"\n🎯 TOTALES DEL SISTEMA:")
        print(f"   Lecturas procesadas: {total_lecturas}")
        print(f"   Anomalías detectadas: {total_anomalias}")
        if total_lecturas > 0:
            print(f"   Tasa global de anomalías: {(total_anomalias/total_lecturas)*100:.2f}%")
        
        print(f"\n✅ Sistema finalizado correctamente")
