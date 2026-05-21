# IDS Backend - Machine Learning-based Intrusion Detection System

Backend API for the Machine Learning-based Intrusion Detection System (IDS) project.

## Features

- **ML Models**: Random Forest, XGBoost, Ensemble (Voting Classifier)
- **Real-time Detection**: Fast inference pipeline for network traffic analysis
- **Alert Engine**: Intelligent alert generation with severity levels
- **WebSocket Support**: Real-time updates for dashboard
- **Email Notifications**: SMTP-based alert notifications
- **Explainable AI**: SHAP and LIME explanations for predictions
- **REST API**: Comprehensive API for alerts, predictions, models, and whitelist management
- **Database**: PostgreSQL for structured data, MongoDB for logs, Redis for caching

## Technology Stack

- **Language**: Python 3.10+
- **Web Framework**: FastAPI
- **ML Frameworks**: Scikit-learn, XGBoost, TensorFlow
- **Database**: PostgreSQL, MongoDB, Redis
- **XAI**: SHAP, LIME
- **Testing**: Pytest
- **Deployment**: Docker, Docker Compose

## Project Structure

```
ids-backend/
├── backend/
│   ├── main.py                 # FastAPI application entry point
│   ├── config.py               # Configuration management
│   ├── api/
│   │   ├── routes.py           # API route handlers
│   │   └── websocket.py        # WebSocket manager
│   ├── database/
│   │   ├── models.py           # SQLAlchemy ORM models
│   │   ├── connection.py       # Database connections
│   │   └── init_db.py          # Database initialization
│   ├── ml/
│   │   ├── models.py           # ML model implementations
│   │   ├── training.py         # Model training script
│   │   ├── inference.py        # Inference pipeline
│   │   └── xai.py              # Explainable AI module
│   ├── alerts/
│   │   └── engine.py           # Alert generation engine
│   ├── notifications/
│   │   └── email.py            # Email notification service
│   └── tests/
│       ├── test_alerts.py      # Alert engine tests
│       └── test_models.py      # ML model tests
├── models/                     # Trained model files
├── logs/                       # Application logs
├── data/                       # Training data
├── requirements.txt            # Python dependencies
├── .env.example               # Environment variables template
├── Dockerfile                 # Docker configuration
├── docker-compose.yml          # Docker Compose configuration
└── README.md                  # This file
```

## Installation

### Prerequisites

- Python 3.10 or higher
- PostgreSQL 14+
- MongoDB 6+
- Redis 7+
- Docker (optional, for containerized deployment)

### Local Setup

1. **Clone the repository**
```bash
git clone <repository-url>
cd ids-backend
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment variables**
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. **Initialize database**
```bash
python backend/database/init_db.py
```

6. **Run the application**
```bash
uvicorn backend.main:app --reload
```

The API will be available at `http://localhost:8000`

### Docker Setup

1. **Build and run with Docker Compose**
```bash
docker-compose up -d
```

2. **Check status**
```bash
docker-compose ps
```

3. **View logs**
```bash
docker-compose logs -f ids-backend
```

4. **Stop services**
```bash
docker-compose down
```

## Usage

### Regenerate dummy ensemble models (local testing)

The live pipeline loads artifacts via `ModelLoader.load_from_directory("ensemble")`, which expects:

- `models/ensemble.pkl`
- `models/ensemble_scaler.pkl`
- `models/ensemble_encoder.pkl`

From the project root:

```bash
python backend/ml/create_dummy_models.py
python scripts/validate_features.py
python scripts/test_predictor.py
```

This script fits a `StandardScaler` on **20** features (from `models/features.json`), trains a small `RandomForestClassifier` on scaled data, and writes a `LabelEncoder` with classes: Normal, DDoS, PortScan, BruteForce, Botnet, Abnormal. Legacy filenames (`scaler.pkl`, `label_encoder.pkl`, etc.) are removed automatically.

### Training Models

Train a model on your dataset:

```bash
python backend/ml/training.py --data path/to/dataset.csv --model ensemble
```

Available models:
- `rf`: Random Forest
- `xgb`: XGBoost
- `ensemble`: Ensemble (Random Forest + XGBoost)

### Sniffer control (IDS pipeline)

Start/stop the **full pipeline** (capture → flows → ML → alerts). There is only one official API:

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/sniffer/start` | Start pipeline (`interface`, `filter_expr`, `model_name`, `min_packets`) |
| GET | `/api/sniffer/status` | Running state and statistics |
| POST | `/api/sniffer/stop` | Stop pipeline |

Traffic routes under `/api/traffic/*` are **monitoring only** (stats, flows, top-talkers) and do not start capture.

```bash
curl http://localhost:8000/health
curl -X POST "http://localhost:8000/api/sniffer/start?interface=eth0&model_name=ensemble"
curl http://localhost:8000/api/sniffer/status
curl http://localhost:8000/api/traffic/stats
curl -X POST http://localhost:8000/api/sniffer/stop
```

### Making Predictions

**Single Prediction:**
```bash
curl -X POST http://localhost:8000/api/predictions \
  -H "Content-Type: application/json" \
  -d '{"feature_1": 1.0, "feature_2": 2.0}'
```

**Batch Prediction:**
```bash
curl -X POST http://localhost:8000/api/predictions/batch \
  -H "Content-Type: application/json" \
  -d '[{"feature_1": 1.0}, {"feature_1": 2.0}]'
```

### Managing Alerts

**Get all alerts:**
```bash
curl http://localhost:8000/api/alerts
```

**Resolve an alert:**
```bash
curl -X PUT http://localhost:8000/api/alerts/{alert_id}/resolve \
  -H "Content-Type: application/json" \
  -d '{"notes": "Investigated"}'
```

### Whitelist Management

**Add IP to whitelist:**
```bash
curl -X POST http://localhost:8000/api/whitelist \
  -H "Content-Type: application/json" \
  -d '{"ip_address": "192.168.1.100", "reason": "Internal server"}'
```

## API Documentation

Interactive API documentation is available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

For detailed API documentation, see [API_DOCUMENTATION.md](API_DOCUMENTATION.md)

## Testing

Run unit tests:

```bash
pytest backend/tests/
```

Run with coverage:

```bash
pytest backend/tests/ --cov=backend --cov-report=html
```

## Configuration

Key environment variables (see `.env.example`):

- `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`: PostgreSQL connection
- `MONGODB_HOST`, `MONGODB_PORT`: MongoDB connection
- `REDIS_HOST`, `REDIS_PORT`: Redis connection
- `ALERT_THRESHOLD_CRITICAL`, `ALERT_THRESHOLD_HIGH`, `ALERT_THRESHOLD_MEDIUM`: Alert severity thresholds
- `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`: Email notification settings

## Architecture

### Components

1. **ML Models**: Implements Random Forest, XGBoost, and Ensemble classifiers
2. **Alert Engine**: Generates alerts based on ML predictions with severity levels
3. **Inference Pipeline**: Real-time prediction pipeline with feature preprocessing
4. **API Layer**: RESTful API endpoints for all system operations
5. **WebSocket Manager**: Real-time updates for connected clients
6. **Email Service**: SMTP-based notification system
7. **XAI Module**: SHAP and LIME explanations for model predictions

### Data Flow

```
Network Traffic → Feature Extraction → ML Prediction → Alert Generation → Database/API
```

## Performance

- **Inference Latency**: <10ms per prediction
- **Throughput**: >1000 predictions/second
- **Model Accuracy**: >95% on CICIDS2017 dataset
- **False Positive Rate**: <3%

## Development

### Adding New Models

1. Create a new model class inheriting from `IDSModel` in `backend/ml/models.py`
2. Implement `train()` and `predict()` methods
3. Add training logic to `backend/ml/training.py`
4. Update model loading in `backend/api/routes.py`

### Adding New API Endpoints

1. Add route handler in `backend/api/routes.py`
2. Update API documentation
3. Add corresponding tests in `backend/tests/`

## Troubleshooting

### Common Issues

**Model not loaded error:**
- Ensure you have trained a model using `backend/ml/training.py`
- Check model paths in `.env` file

**Database connection error:**
- Verify PostgreSQL/MongoDB/Redis are running
- Check connection settings in `.env` file

**Packet capture permission error:**
- Run with appropriate permissions (sudo or Docker with NET_RAW capability)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

This project is part of a graduation project for academic purposes.

## Contact

For questions or support, please contact the development team.

## Acknowledgments

- CICIDS2017 Dataset
- Scikit-learn, XGBoost, TensorFlow communities
- FastAPI framework
