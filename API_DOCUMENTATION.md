# IDS Backend API Documentation

## Base URL
```
http://localhost:8000
```

## Authentication
Currently using basic authentication. JWT authentication will be added in future versions.

## Endpoints

### Health Check
```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "IDS Backend",
  "version": "1.0.0"
}
```

---

### Alerts

#### Get All Alerts
```http
GET /api/alerts
```

**Query Parameters:**
- `skip` (int): Number of records to skip (default: 0)
- `limit` (int): Number of records to return (default: 100)
- `severity` (str): Filter by severity (critical, high, medium, low)
- `status` (str): Filter by status (active, resolved, ignored)

**Response:**
```json
[
  {
    "id": 1,
    "alert_id": "uuid",
    "source_ip": "192.168.1.100",
    "dest_ip": "192.168.1.1",
    "source_port": 12345,
    "dest_port": 80,
    "attack_type": "DDoS",
    "severity": "critical",
    "confidence": 0.95,
    "timestamp": "2024-01-01T00:00:00",
    "status": "active",
    "is_resolved": false,
    "resolved_at": null,
    "notes": null,
    "model_name": "RandomForest",
    "model_version": "1.0"
  }
]
```

#### Get Alert by ID
```http
GET /api/alerts/{alert_id}
```

**Response:** Same as above (single object)

#### Resolve Alert
```http
PUT /api/alerts/{alert_id}/resolve
```

**Body:**
```json
{
  "notes": "Investigated and confirmed as false positive"
}
```

#### Delete Alert
```http
DELETE /api/alerts/{alert_id}
```

---

### Predictions

#### Single Prediction
```http
POST /api/predictions
```

**Body:**
```json
{
  "feature_1": 1.0,
  "feature_2": 2.0,
  ...
}
```

**Response:**
```json
{
  "class": "DDoS",
  "confidence": 0.95,
  "model_name": "RandomForest",
  "model_version": "1.0",
  "all_probabilities": {
    "Normal": 0.05,
    "DDoS": 0.95,
    "PortScan": 0.00
  }
}
```

#### Batch Prediction
```http
POST /api/predictions/batch
```

**Body:**
```json
[
  {"feature_1": 1.0, "feature_2": 2.0},
  {"feature_1": 3.0, "feature_2": 4.0}
]
```

**Response:**
```json
{
  "predictions": [
    {"class": "DDoS", "confidence": 0.95},
    {"class": "Normal", "confidence": 0.98}
  ]
}
```

---

### Models

#### Get All Models
```http
GET /api/models
```

**Response:**
```json
[
  {
    "id": 1,
    "model_name": "Random Forest",
    "version": "1.0",
    "algorithm": "RandomForest",
    "accuracy": 0.97,
    "precision": 0.96,
    "recall": 0.95,
    "f1_score": 0.95,
    "is_active": true,
    "created_at": "2024-01-01T00:00:00"
  }
]
```

#### Load Model
```http
POST /api/models/load/{model_id}
```

---

### Whitelist

#### Get Whitelist
```http
GET /api/whitelist
```

#### Add to Whitelist
```http
POST /api/whitelist
```

**Body:**
```json
{
  "ip_address": "192.168.1.100",
  "port": 80,
  "protocol": "TCP",
  "reason": "Internal server"
}
```

#### Remove from Whitelist
```http
DELETE /api/whitelist/{whitelist_id}
```

---

### Statistics

#### Get Alert Engine Stats
```http
GET /api/stats/alert-engine
```

#### Get System Stats
```http
GET /api/stats/system
```

---

### WebSocket

#### Real-time Updates
```
ws://localhost:8000/ws
```

**Message Types:**
- `alert`: New alert generated
- `traffic`: Traffic update
- `status`: System status update

---

## Error Responses

All endpoints may return:

```json
{
  "detail": "Error message"
}
```

Status codes:
- 400: Bad Request
- 404: Not Found
- 500: Internal Server Error
- 503: Service Unavailable (model not loaded)
