# core/modelo.py
import joblib
import numpy as np
import pandas as pd
from sklearn.exceptions import InconsistentVersionWarning
import warnings

warnings.filterwarnings("ignore", category=InconsistentVersionWarning)

class ModeloAnomalias:
    def __init__(self, scaler_path="models/scaler_datos.pkl", modelo_path="models/modelo_isolation_forest.pkl"):
        self.scaler_path = scaler_path
        self.modelo_path = modelo_path
        self.modelo_cargado = False
        self._cargar_modelos()

    def _cargar_modelos(self):
        try:
            self.scaler = joblib.load(self.scaler_path)
            self.modelo = joblib.load(self.modelo_path)
            self.modelo_cargado = True
            print("✅ Modelos cargados correctamente")
        except Exception as e:
            print(f"❌ Error cargando modelos: {e}")

    def verificar_estado_completo(self, temp, volt, efic, efic_ant=None):
        alerta_modelo = 0
        if self.modelo_cargado:
            try:
                entrada = pd.DataFrame([[temp, volt, efic]], columns=['Temperatura_C', 'Voltaje_V', 'Eficiencia_%'])
                entrada_scaled = self.scaler.transform(entrada)
                pred = self.modelo.predict(entrada_scaled)
                alerta_modelo = int(pred[0] == -1)
            except Exception as e:
                print(f"⚠ Error modelo: {e}")

        alerta_voltaje = int(volt < 210)
        alerta_temp = int(temp > 80)
        alerta_eficiencia = int((efic - efic_ant) < -2.0) if efic_ant is not None else 0

        fuentes = []
        if alerta_modelo: fuentes.append("Modelo_ML")
        if alerta_voltaje: fuentes.append("Bajo_Voltaje")
        if alerta_temp: fuentes.append("Alta_Temperatura")
        if alerta_eficiencia: fuentes.append("Caida_Eficiencia")
        if not fuentes: fuentes = ["Normal"]

        return {
            "alerta_total": bool(alerta_modelo or alerta_voltaje or alerta_temp or alerta_eficiencia),
            "fuente_alerta": fuentes,
            "delta_efic": (efic - efic_ant) if efic_ant is not None else None,
            "alertas_individuales": {
                "modelo_ml": bool(alerta_modelo),
                "bajo_voltaje": bool(alerta_voltaje),
                "alta_temperatura": bool(alerta_temp),
                "caida_eficiencia": bool(alerta_eficiencia)
            }
        }

