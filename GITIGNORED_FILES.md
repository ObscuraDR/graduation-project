# Danh sách thư mục/file không được đẩy lên Git

## Secrets / Config
| Đường dẫn | Lý do |
|---|---|
| `.env` | Chứa API keys, secret keys, passwords |

## Data lớn
| Đường dẫn | Lý do |
|---|---|
| `backend/data/cicids2017/` | Dataset CICIDS2017 (file CSV >100MB, vượt giới hạn GitHub) |

## Generated / Build
| Đường dẫn | Lý do |
|---|---|
| `frontend/dist/` | React build output |
| `frontend/node_modules/` | npm packages |
| `logs/` | Runtime logs |

## Cache / Temp
| Đường dẫn | Lý do |
|---|---|
| `.pytest_cache/` | Pytest cache |
| `backend/**/__pycache__/` | Python bytecode cache |

## IDE / Tool Configs
| Đường dẫn | Lý do |
|---|---|
| `.vscode/` | VSCode workspace settings |
| `.qodo/` | Qodo tool config |
| `.sixth/` | Sixth tool config |

---

> Tất cả các mục trên đã được khai báo trong `.gitignore` và sẽ không bao giờ bị push lên GitHub.
> File `.env.example` (không chứa giá trị thật) vẫn được track để làm template.
