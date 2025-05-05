import re
from typing import Dict, List, Tuple

import gspread
import pandas as pd
import streamlit as st
from google.oauth2 import service_account
from gspread_dataframe import get_as_dataframe

# Configuration
SHEET_URL = "https://docs.google.com/spreadsheets/d/1zBrHhsj2ryzC3c6KwIw-9QZMOjiU4zYLlRFvQiGBukg/edit#gid=2040181610"
SHEETS = {
    "asymmetries": "BASE Asimetrias del Cerebro",
    "exercises": "BASE Ejercicios"
}

class DataManager:
    @st.cache_resource
    def connect_to_gsheets():
        """Create a connection to Google Sheets."""
        credentials = service_account.Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
        )
        return gspread.authorize(credentials)

    @st.cache_data(ttl=600)
    def load_data(sheet_url: str, sheet_name: str) -> pd.DataFrame:
        """Load and clean data from Google Sheets."""
        try:
            client = DataManager.connect_to_gsheets()
            sh = client.open_by_url(sheet_url)
            worksheet = sh.worksheet(sheet_name)
            df = get_as_dataframe(worksheet, evaluate_formulas=True, skiprows=0)
            return df.dropna(how='all').dropna(axis=1, how='all')
        except Exception as e:
            st.error(f"Error loading data: {str(e)}")
            return pd.DataFrame()

class FilterManager:
    @staticmethod
    def create_sidebar_filters(df: pd.DataFrame, escenarios_col: str) -> Tuple[Dict, Dict]:
        """Create and manage sidebar filters."""
        st.sidebar.header("Filtros")
        
        # Create filters for each column except Escenarios and Descripcion
        filter_cols = [col for col in df.columns if col != escenarios_col and col != "Descripcion"]
        
        filters = {}
        slider_filters = {}
        
        # Define slider columns
        slider_columns = [
            "% Hemisferio Correspondiente al ojo (Natural)",
            "% de Hemisferio Recesivo (Anitnatural)"
        ]
        
        for col_name in filter_cols:
            if col_name in slider_columns:
                slider_filters[col_name] = st.sidebar.slider(
                    f"Filtrar por {col_name}",
                    min_value=0,
                    max_value=100,
                    value=50,
                    step=1
                )
            else:
                unique_values = sorted(df[col_name].dropna().unique())
                filters[col_name] = st.sidebar.multiselect(
                    f"Filtrar por {col_name}",
                    options=unique_values,
                    default=[]
                )
        
        return filters, slider_filters

    @staticmethod
    def apply_filters(df: pd.DataFrame, filters: Dict, slider_filters: Dict) -> Tuple[pd.DataFrame, bool]:
        """Apply filters to the dataframe."""
        filtered_df = df.copy()
        any_filter_applied = False
        
        # Apply regular filters
        for col, selected_values in filters.items():
            if selected_values:
                any_filter_applied = True
                filtered_df = filtered_df[filtered_df[col].isin(selected_values)]
        
        # Apply slider filters
        for col, selected_value in slider_filters.items():
            if selected_value != 50:
                any_filter_applied = True
                mask = FilterManager.create_percentage_mask(filtered_df, col, selected_value)
                filtered_df = filtered_df[mask]
        
        return filtered_df, any_filter_applied

    @staticmethod
    def create_percentage_mask(df: pd.DataFrame, col: str, value: int) -> pd.Series:
        """Create a mask for percentage range filtering."""
        return df.apply(
            lambda row: (
                not pd.isna(row[col]) and 
                FilterManager.is_in_percentage_range(value, row[col])
            ),
            axis=1
        )

    @staticmethod
    def is_in_percentage_range(value: int, range_str: str) -> bool:
        """Check if a value falls within a percentage range."""
        if pd.isna(range_str):
            return False
        
        numbers = re.findall(r'\d+', str(range_str))
        if len(numbers) == 1:
            return value == int(numbers[0])
        elif len(numbers) == 2:
            return int(numbers[0]) <= value <= int(numbers[1])
        return False

class ExerciseManager:
    @staticmethod
    def create_exercise_filters(df: pd.DataFrame) -> Dict[str, List]:
        """Create filters for the exercises table."""
        st.header("Ejercicios")
        
        col1, col2 = st.columns(2)
        filters = {}
        
        with col1:
            filters['Filmina'] = st.multiselect(
                'Filtrar por Filmina',
                options=sorted(df['Filmina'].unique()),
                default=[]
            )
            filters['Nivel de Ejercicio'] = st.multiselect(
                'Filtrar por Nivel de Ejercicio',
                options=sorted(df['Nivel de Ejercicio'].unique()),
                default=[]
            )
        
        with col2:
            filters['Dificultad'] = st.multiselect(
                'Filtrar por Dificultad',
                options=sorted(df['Dificultad'].unique()),
                default=[]
            )
            filters['Dificultad de Nivel Ejercicio'] = st.multiselect(
                'Filtrar por Dificultad de Nivel Ejercicio',
                options=sorted(df['Dificultad de Nivel Ejercicio'].unique()),
                default=[]
            )
        
        return filters

    @staticmethod
    def apply_exercise_filters(df: pd.DataFrame, filters: Dict[str, List]) -> pd.DataFrame:
        """Apply filters to the exercises dataframe."""
        filtered_df = df.copy()
        for col, selected_values in filters.items():
            if selected_values:
                filtered_df = filtered_df[filtered_df[col].isin(selected_values)]
        return filtered_df

def main():
    # Page configuration
    st.set_page_config(page_title="SphinxAI App", page_icon="📊", layout="wide")
    st.title("SphinxAI")
    
    try:
        # Load initial data
        df_asymmetries = DataManager.load_data(SHEET_URL, SHEETS["asymmetries"])
        df_exercises = DataManager.load_data(SHEET_URL, SHEETS["exercises"])
        
        if df_asymmetries.empty or df_exercises.empty:
            st.error("No se pudieron cargar los datos. Por favor, verifica la conexión.")
            return
        
        # Find Escenarios column
        escenarios_col = next((col for col in df_asymmetries.columns if "Escenario" in col), 
                            df_asymmetries.columns[-1])
        
        # Create and apply main filters
        filters, slider_filters = FilterManager.create_sidebar_filters(df_asymmetries, escenarios_col)
        filtered_df, any_filter_applied = FilterManager.apply_filters(df_asymmetries, filters, slider_filters)
        
        # Display filtered results
        st.header("Resultado del Test")
        st.subheader("Datos Filtrados")
        st.dataframe(filtered_df)
        
        # Handle scenario selection and exercise filtering
        all_escenarios = filtered_df[escenarios_col].dropna().unique()
        with st.sidebar:
            st.header("Selección de Escenarios")
            selected_escenarios = st.multiselect(
                "Selecciona los Escenarios:",
                options=all_escenarios,
                default=all_escenarios[:5] if len(all_escenarios) > 5 else all_escenarios
            )
        
        if selected_escenarios:
            # Filter exercises based on scenarios
            exercise_mask = pd.Series(False, index=df_exercises.index)
            for col in [c for c in df_exercises.columns if str(c).startswith("Escenario:")]:
                df_exercises[col] = df_exercises[col].astype(str)
                for escenario in selected_escenarios:
                    exercise_mask |= df_exercises[col].str.contains(escenario, na=False)
            
            filtered_exercises = df_exercises[exercise_mask]
            
            if not filtered_exercises.empty:
                # Apply additional exercise filters
                exercise_filters = ExerciseManager.create_exercise_filters(filtered_exercises)
                final_exercises = ExerciseManager.apply_exercise_filters(filtered_exercises, exercise_filters)
                
                st.dataframe(final_exercises)
                
                # Export option
                st.download_button(
                    label="Descargar datos filtrados como CSV",
                    data=final_exercises.to_csv(index=False).encode('utf-8'),
                    file_name='filtered_exercises.csv',
                    mime='text/csv',
                )
            else:
                st.warning("No se encontraron ejercicios que coincidan con los criterios seleccionados.")
        else:
            st.warning("Por favor, selecciona al menos un Escenario para filtrar los ejercicios.")
            
    except Exception as e:
        st.error(f"Error en la aplicación: {str(e)}")

if __name__ == "__main__":
    main()
