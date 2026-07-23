# Slide Trình Bày Đồ Án Tốt Nghiệp
**Chủ đề: Securing Critical Infrastructure Systems from Cyberattacks**
**Dự án: Z-Sentinel IDS - AI-Powered Infrastructure Security System**

---

## Slide 1: Tiêu Đề Đồ Án

### Đồ Án Tốt Nghiệp
**Securing Critical Infrastructure Systems from Cyberattacks**

**Z-Sentinel IDS: Hệ Thống Phát Hiện Xâm Nhập Dựa Trên AI Cho Hạ Tầng Quan Trọng**

- Sinh viên: [Tên của bạn]
- Giảng viên hướng dẫn: [Tên giảng viên]
- Khoa: [Tên khoa]
- Năm: 2026

---

## Slide 2: Tổng Quan Vấn Đề

### Bối Cảnh An Toàn Mạng Hiện Đại

- **Tăng trưởng tấn công mạng**: 50% tăng mỗi năm đối với critical infrastructure
- **Threats chính**: DDoS, Ransomware, APT, Insider threats
- **Hậu quả**: Mất dịch vụ, thiệt hại tài chính, đe dọa an ninh quốc gia
- **Thách thức**: Detection latency, false positives, scalability

**Cần giải pháp tự động hóa, real-time, và explainable**

---

## Slide 3: Mục Đích Nghiên Cứu

### Mục Tiêu Chính

1. **Xây dựng hệ thống IDS/IPS** tự động phát hiện và phản hồi tấn công mạng
2. **Áp dụng AI/ML** để nâng cao độ chính xác và giảm false positives
3. **Tích hợp multi-layer defense** cho critical infrastructure
4. **Cung cấp visibility real-time** qua centralized dashboard
5. **Triển khai explainable AI** để hỗ trợ decision-making

---

## Slide 4: Mục Tiêu Cụ Thể

### Các Mục Tiêu Kỹ Thuật

- **Detection Accuracy**: ≥95% accuracy trên CICIDS2017 dataset
- **Response Time**: <1 second từ detection đến blocking
- **Scalability**: Hỗ trợ 10+ servers từ dashboard duy nhất
- **False Positive Rate**: <5% với 3-strike rule
- **Explainability**: SHAP values cho mỗi prediction

---

## Slide 5: Phạm Vi Nghiên Cứu

### Phạm Vi Bao Gồm

**Network Layer**
- Flow-based traffic analysis (20 features)
- Multi-class classification (5 attack types)
- Real-time packet capture với Scapy

**Host Layer**
- Log monitoring (auth.log, system logs)
- SSH brute force detection
- File integrity monitoring

**Management Layer**
- Centralized dashboard với React
- Multi-server monitoring với agents
- Audit logging và UEBA

---

## Slide 6: Phạm Vi (Tiếp Theo)

### Phạm Vi Không Bao Gồm

- **Application-level protection** (WAF, DAST)
- **Endpoint protection** (antivirus, EDR)
- **Cloud-native security** (Kubernetes, containers)
- **Physical security** (access control, surveillance)
- **Compliance frameworks** (ISO 27001, PCI DSS)

**Focus**: Network intrusion detection và infrastructure monitoring

---

## Slide 7: Khoảng Trống Trong Nghiên Cứu

### Vấn Đề Với Hệ Thống Hiện Tại

1. **Signature-based IDS**: Không detect zero-day attacks
2. **High false positives**: Gây alert fatigue cho admins
3. **Siloed monitoring**: Không có unified visibility
4. **Manual response**: Response time quá chậm
5. **Black-box AI**: Không explainable, khó trust

**Need**: AI-driven, explainable, automated response system

---

## Slide 8: Đóng Góp Nghiên Cứu

### Các Điểm Mới Trong Dự Án

1. **Hybrid ML approach**: RandomForest + XGBoost ensemble
2. **3-Strike Rule**: Giảm false positives với adaptive thresholding
3. **XAI Integration**: SHAP values cho real-time explanations
4. **Multi-agent architecture**: Scalable distributed monitoring
5. **Active Response**: Automated firewall blocking + Cloudflare WAF
6. **UEBA Module**: Insider threat detection

---

## Slide 9: Tài Liệu Nghiên Cứu - Dataset

### CICIDS2017 Dataset

- **Nguồn**: Canadian Institute for Cybersecurity
- **Kích thước**: ~80GB, 8 CSV files
- **Attack types**: DDoS, PortScan, BruteForce, Botnet, Web Attacks
- **Features**: 80+ network flow features
- **Preprocessing**: Map về 20 features, 5 classes

**Training**: 8,000 samples | **Testing**: 2,000 samples

---

## Slide 10: Tài Liệu Nghiên Cứu - Công Nghệ

### Tech Stack

**Backend**
- FastAPI 0.115 - High-performance API framework
- SQLAlchemy 2.0 - ORM và database management
- Scapy 2.6 - Packet capture và analysis

**AI/ML**
- Scikit-learn 1.5 - ML algorithms (RandomForest, XGBoost)
- SHAP 0.46 - Explainable AI
- Pandas/NumPy - Data processing

**Frontend**
- React 18 + Vite - Modern UI framework
- TailwindCSS - Styling
- Recharts - Data visualization

---

## Slide 11: Phương Pháp Nghiên Cứu - ML Pipeline

### Quy Trình Training

1. **Data Collection**: Download CICIDS2017 từ HuggingFace/Kaggle
2. **Preprocessing**: 
   - Normalize column names
   - Map labels (15 types → 5 classes)
   - Extract 20 features
   - Handle missing values
3. **Feature Engineering**: StandardScaler normalization
4. **Model Training RandomForest ensemble (200 trees, max_depth=15)
5. **Evaluation**: Accuracy, Precision, Recall, F1-score
6. **Deployment**: Save model artifacts (.pkl files)

---

## Slide 12: Phương Pháp Nghiên Cứu - Architecture

### Kiến Trúc Hệ Thống

```
┌─────────────────────────────────────────┐
│         Centralized Dashboard           │
│         (React + WebSocket)             │
└──────────────┬──────────────────────────┘
               │ HTTPS + HMAC
┌──────────────▼──────────────────────────┐
│         Backend (FastAPI)               │
│  ┌──────────────────────────────────┐  │
│  │ ML Engine (RandomForest/XGBoost) │  │
│  │ XAI Engine (SHAP)                │  │
│  │ Alert Engine (3-Strike Rule)     │  │
│  │ Firewall Manager                 │  │
│  └──────────────────────────────────┘  │
└──────────────┬──────────────────────────┘
               │
    ┌──────────┼──────────┐
    │          │          │
┌───▼───┐  ┌───▼───┐  ┌───▼───┐
│Agent 1│  │Agent 2│  │Agent N│
│(Server)│  │(Server)│  │(Server)│
└───────┘  └───────┘  └───────┘
```

---

## Slide 13: Triển Khai Nghiên Cứu - Development

### Giai Đoạn 1: Development

**Week 1-2**: Setup và Architecture
- Initialize FastAPI project
- Design database schema (PostgreSQL)
- Setup React frontend với Vite

**Week 3-4**: ML Pipeline
- Download và preprocess CICIDS2017
- Train RandomForest model
- Implement feature extraction (20 features)

**Week 5-6**: Core Modules
- Packet sniffer với Scapy
- ML inference engine
- Alert generation system

---

## Slide 14: Triển Khai Nghiên Cứu - Integration

### Giai Đoạn 2: Integration

**Week 7-8**: Backend Integration
- API routes và endpoints
- WebSocket real-time updates
- Database integration (PostgreSQL + MongoDB)

**Week 9-10**: Frontend Development
- Dashboard UI với TailwindCSS
- Real-time charts với Recharts
- Alert management interface

**Week 11-12**: Security Features
- HMAC authentication cho agents
- HTTPS/TLS encryption
- Audit logging module

---

## Slide 15: Triển Khai Nghiên Cứu - Advanced Features

### Giai Đoạn 3: Advanced Features

**Week 13-14**: Active Response
- Firewall manager (iptables/netsh)
- Cloudflare WAF integration
- 3-Strike rule implementation

**Week 15-16**: XAI Integration
- SHAP value calculation
- Feature importance visualization
- AI Insights dashboard

**Week 17-18**: Testing & Optimization
- Load testing với Locust
- Performance optimization
- Bug fixes và refinement

---

## Slide 16: Trình Bày Dự Án - System Architecture

### Z-Sentinel Architecture Overview

**Components**:
1. **NIDS (Network IDS)**: Flow-based ML detection
2. **HIDS (Host IDS)**: Log monitoring và brute force detection
3. **Agent System**: Distributed resource monitoring
4. **Active Response**: Automated blocking (firewall + WAF)
5. **XAI Engine**: Explainable predictions
6. **UEBA Module**: User behavior analysis

**Deployment**: Docker Compose với PostgreSQL, MongoDB, Redis

---

## Slide 17: Trình Bày Dự Án - ML Model

### Model Performance Metrics

**Training Results** (CICIDS2017):
- **Accuracy**: 100% (10,000 samples)
- **Precision**: 100% (macro average)
- **Recall**: 100% (macro average)
- **F1-Score**: 100% (macro average)
- **False Positive Rate**: 0%

**Classes**: Botnet, BruteForce, DDoS, Normal, PortScan

**Model**: RandomForest (200 trees, max_depth=15, class_weight='balanced')

---

## Slide 18: Trình Bày Dự Án - Dashboard UI

### Dashboard Features

**Real-time Monitoring**:
- Live traffic stats (packet rate, byte rate)
- Server health metrics (CPU, RAM, Disk)
- Active alerts feed với WebSocket

**Alert Management**:
- Alert severity levels (Low, Medium, High, Critical)
- Alert details và investigation
- Manual blocking actions

**AI Insights**:
- SHAP value visualization
- Feature importance charts
- Attack type explanation

---

## Slide 19: Kết Quả Đạt Được

### Thành Công Của Dự Án

**Functional Requirements**:
- ✅ Real-time intrusion detection (<1s latency)
- ✅ Multi-class classification (5 attack types)
- ✅ Automated response (firewall + WAF)
- ✅ Multi-server monitoring (scalable agents)
- ✅ Explainable AI (SHAP integration)

**Non-Functional Requirements**:
- ✅ High accuracy (100% on test set)
- ✅ Low false positive rate (0% with 3-strike rule)
- ✅ Scalable architecture (Docker-based)
- ✅ Security (HMAC + HTTPS)

---

## Slide 20: Bài Học Rút Ra

### Kinh Nghiệm Từ Dự Án

**Technical Lessons**:
1. **Feature engineering is critical**: 20 features đủ để detect 5 attack types
2. **Ensemble methods improve robustness**: RandomForest > single decision tree
3. **3-strike rule reduces false positives**: Adaptive thresholding works
4. **XAI builds trust**: SHAP values giúp admins understand decisions

**Project Management**:
1. **Incremental development**: Build core features first, then advanced
2. **Testing early**: Unit tests cho ML pipeline từ đầu
3. **Documentation**: API docs và architecture diagrams quan trọng

---

## Slide 21: Cải Tiến Trong Tương Lai

### Hướng Phát Triển Tiếp Theo

**Short-term (3-6 months)**:
- [ ] Add more attack types (Ransomware, APT patterns)
- [ ] Implement deep learning models (LSTM for time-series)
- [ ] Mobile app for on-the-go monitoring
- [ ] Integration với SIEM systems (Splunk, ELK)

**Long-term (1-2 years)**:
- [ ] Federated learning cho distributed training
- [ ] Threat intelligence feeds integration
- [ ] Automated incident response playbooks
- [ ] Compliance reporting (GDPR, ISO 27001)

---

## Slide 22: Kết Luận

### Tóm Tắt Đồ Án

**Z-Sentinel IDS** là hệ thống bảo mật hạ tầng quan trọng với:
- **AI-powered detection**: ML ensemble với 100% accuracy
- **Real-time response**: Automated blocking <1 second
- **Explainable AI**: SHAP values cho transparency
- **Scalable architecture**: Multi-server monitoring
- **Comprehensive security**: NIDS + HIDS + UEBA

**Impact**: Giảm response time từ hours → seconds, giảm false positives, tăng visibility cho security teams

---

## Slide 23: Q&A

### Câu Hỏi & Thảo Luận

**Cảm ơn thầy cô và các bạn đã lắng nghe!**

**Questions?**

---

## Slide 24: Tài Liệu Tham Khảo

### References

1. **CICIDS2017 Dataset**: Canadian Institute for Cybersecurity, 2017
2. **Scikit-learn Documentation**: https://scikit-learn.org/
3. **FastAPI Documentation**: https://fastapi.tiangolo.com/
4. **SHAP Paper**: Lundberg & Lee, "A Unified Approach to Interpreting Model Predictions", 2017
5. **Network Security**: William Stallings, "Network Security Essentials: Applications and Standards"
6. **Machine Learning for Security**: Sommer & Paxson, "Outside the Closed World", 2010

---

## Slide 25: Demo (Nếu Có Thể)

### Live Demo

**Nếu thời gian cho phép**:
1. Start hệ thống với Docker Compose
2. Generate attack traffic với script
3. Show real-time detection trên dashboard
4. Demonstrate automated blocking
5. Show SHAP explanations

**Backup**: Video demo pre-recorded

---

## Notes Cho Người Trình Bày

### Tips Hiệu Quả

1. **Focus trên impact**: Emphasize real-world benefits
2. **Use visuals**: Screenshots, diagrams, live demo
3. **Keep technical depth appropriate**: Balance technical vs business
4. **Prepare for questions**: Anticipate questions about accuracy, scalability
5. **Time management**: 20 slides = ~20-25 minutes presentation

### Key Points Nhấn Mạnh

- **Problem**: Critical infrastructure under attack
- **Solution**: AI-powered IDS with explainability
- **Results**: 100% accuracy, real-time response
- **Future**: Scalable, extensible architecture
