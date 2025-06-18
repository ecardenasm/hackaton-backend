import numpy as np
import pandas as pd
import threading
import time
from datetime import datetime
from collections import deque
import queue 

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
            'ultima_lectura': self.ultima_lectura if self.ultima_lectura else None,
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
                'fuentes_alerta': ','.join(lectura['fuentes_alerta']),

                'delta_eficiencia': lectura.get('delta_efic')

            }
            
            # Agregar alertas individuales
            for alerta, activa in lectura['alertas_individuales'].items():
                fila[f'alerta_{alerta}'] = activa
            
            datos.append(fila)
        
        return pd.DataFrame(datos)

