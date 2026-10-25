<div align="center">

# ⚖️ Desemppa

**Asistente legal personal y local para el ordenamiento jurídico español.**  
*Pipeline dialéctico de 4 fases, cortafuegos anti-alucinación, verificación en tiempo real contra el BOE y coste marginal de 0 €.*

[![Python](https://img.shields.io/badge/Python-3.12-blue.svg?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61DAFB.svg?logo=react&logoColor=black)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.5-3178C6.svg?logo=typescript&logoColor=white)](https://www.typescriptlang.org)
[![Tests](https://img.shields.io/badge/Tests-357%20passed-brightgreen.svg)](#)
[![Privacidad](https://img.shields.io/badge/Privacidad-100%25%20Local%20(DPAPI)-success.svg)](#)

</div>

---

> ⚠️ **Aviso de Responsabilidad:** Herramienta experimental de autodefensa jurídica e información legal para uso personal. **No constituye asesoramiento legal profesional.**

---

## 🌟 ¿Qué es Desemppa?

La mayoría de modelos de IA cometen fallos graves en derecho: inventan artículos, calculan mal los plazos de caducidad y se lavan las manos con respuestas ambiguas. 

**Desemppa** soluciona esto eliminando la dependencia ciega del LLM mediante un **pipeline determinista de 4 fases**:
1. **Triaje y Detección de Hechos:** Extrae fechas estrictamente reales del usuario y selecciona la materia jurídica.
2. **Ingesta Oficial:** Descarga y sincroniza la versión de la ley vigente a la fecha de los hechos desde el **BOE**, **EUR-Lex** (Unión Europea) y **Convenios Colectivos REGCON**.
3. **Juicio Dialéctico:** Genera un debate contradictorio paralelo entre **Defensa** y **Contraparte**, resuelto por un **Magistrado** con lógica disyuntiva estricta (*sin medias tintas*).
4. **Cortafuegos Anti-Invención y Certificación:** Un motor en código que escanea cada cita normativa y la contrasta contra el texto oficial con coincidencia literal `RapidFuzz >= 92%`. Si no está en el BOE, se elimina.

---

## ✨ Características Principales

* 🔒 **100% Local y Privado:** Tus consultas no se comparten. Datos sensibles anonimizados con PII Redactor y claves cifradas con Windows DPAPI.
* 💸 **0 € de coste extra por token:** Funciona sobre tus suscripciones mensuales planas habituales (**Google AI Pro vía Antigravity** y **Claude Pro vía Claude Code**), además de soportar cualquier proveedor por API (OpenAI, Grok, DeepSeek, Mistral, OpenRouter).
* 📅 **Motor de Plazos Determinista:** Los plazos de caducidad, prescripción y días hábiles no los calcula el LLM, sino un motor de calendario judicial con festivos nacionales, autonómicos y locales.
* ⚖️ **Especialidades Forales y MASC (LO 1/2025):** Aplica automáticamente el Código Civil de Cataluña (prescripciones trienales) y el requisito preceptivo de mediación previa en demandas civiles.
* 📄 **Borradores y Hojas de Ruta sin LLM:** Generación de burofaxes y escritos procesales mediante plantillas deterministas uniendo tu relato con las normas verificadas del BOE.
* 🌐 **Compartir en Red Local (LAN):** Servidor seguro para permitir que otros dispositivos de tu casa/oficina prueben la app mediante código QR con token de invitado independiente.

---

## 🚀 Inicio Rápido (Windows)

### Requisitos Previos
* **Python 3.12+** (gestionado con [`uv`](https://docs.astral.sh/uv/))
* **Node.js 18+** y `npm`
* CLI de **Antigravity (`agy`)** o **Claude Code (`claude`)** configurado.

### Instalación en 3 pasos

```powershell
# 1. Clonar el repositorio
git clone https://github.com/AlvaroLofra/Desemppa.git
cd Desemppa

# 2. Instalar dependencias
uv sync
cd web ; npm install ; cd ..

# 3. Arrancar la aplicación
.\INICIAR_DESEMPPA.bat
```
*(El script compila el frontend, arranca FastAPI y abre el navegador automáticamente en `http://127.0.0.1:8000`).*

---

## 🧪 Verificación y Calidad

El proyecto cuenta con una batería de pruebas automatizadas completa:
```powershell
uv run pytest -q               # 357 tests unitarios y de contrato
uv run ruff check .            # Linter estricto de código
uv run mypy                    # Comprobación de tipos en 54 ficheros
cd web ; npx vitest run        # Tests unitarios del frontend React
```
