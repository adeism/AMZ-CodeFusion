# 📘 Panduan Cepat AMZ-CodeFusion

Panduan singkat untuk menggunakan AMZ-CodeFusion dengan fitur-fitur baru.

---

## 🎯 Cara Tercepat Memulai

### GUI Mode (Visual)
```bash
python CodeFusion.py
```
Klik tombol, pilih opsi, selesai!

### CLI Mode (Terminal)
```bash
python CodeFusion.py --cli -s ./myproject -o output.txt
```

---

## ⚡ Perintah Paling Berguna

### 1. Preview Dulu (Dry Run)
```bash
python CodeFusion.py --cli -s ./project -o out.txt --dry-run
```
Lihat apa yang akan diproses tanpa menulis file.

### 2. Buat Dataset untuk RAG
```bash
python CodeFusion.py --cli -s ./code -o dataset.json \
    --format json --smart-chunk --deduplicate
```
Output JSON optimal untuk vector databases.

### 3. Bersihkan Comments
```bash
python CodeFusion.py --cli -s ./src -o clean.txt \
    --exclude-comments --exclude-line-comments
```
Hapus `/* */` dan `//` comments.

### 4. Buat Documentation
```bash
python CodeFusion.py --cli -s ./project -o docs.md \
    --format markdown --syntax-highlight
```
Markdown dengan table of contents otomatis.

### 5. Proses Cepat (Multi-thread)
```bash
python CodeFusion.py --cli -s ./large-project -o out.txt -w 16
```
Gunakan 16 threads untuk proses lebih cepat.

---

## 🎨 Format Output

### TXT (Simple)
```bash
-o output.txt
```
Plain text, universal.

### JSON (Structured)
```bash
-o data.json --format json
```
Perfect untuk RAG dan programmatic access.

### Markdown (Beautiful)
```bash
-o docs.md --format markdown
```
Documentation-ready dengan syntax highlighting.

---

## 🔧 Opsi Penting

| Opsi | Fungsi | Contoh |
|------|--------|--------|
| `-s` | Source directory | `-s ./myproject` |
| `-o` | Output file | `-o dataset.json` |
| `-e` | Filter extensions | `-e py,js,ts` |
| `-w` | Worker threads | `-w 8` |
| `--format` | Output format | `--format json` |
| `--dry-run` | Preview mode | `--dry-run` |
| `--deduplicate` | Skip duplicates | `--deduplicate` |
| `--smart-chunk` | Chunk large files | `--smart-chunk` |
| `--exclude-comments` | Remove `/* */` | `--exclude-comments` |
| `--exclude-line-comments` | Remove `//` | `--exclude-line-comments` |
| `--syntax-highlight` | Add code blocks | `--syntax-highlight` |
| `--line-numbers` | Add line numbers | `--line-numbers` |
| `--zip` | Create zip archive | `--zip` |

---

## 💡 Tips & Tricks

### Tip 1: Gunakan Config Presets
Simpan konfigurasi favorit di GUI, lalu load kembali kapan saja.

### Tip 2: Always Dry Run First
```bash
# Preview dulu
python CodeFusion.py --cli -s . -o out.txt --dry-run

# Baru proses beneran
python CodeFusion.py --cli -s . -o out.txt
```

### Tip 3: Optimasi untuk RAG
```bash
python CodeFusion.py --cli -s ./code -o rag.json \
    --format json \
    --smart-chunk \
    --deduplicate \
    --exclude-comments \
    --exclude-line-comments
```

### Tip 4: Exclude Folders
```bash
python CodeFusion.py --cli -s . -o out.txt \
    --exclude-folders ".git,node_modules,venv,test"
```

### Tip 5: Filter Extensions
```bash
# Hanya Python files
python CodeFusion.py --cli -s . -o out.txt -e py

# Python + JavaScript
python CodeFusion.py --cli -s . -o out.txt -e py,js
```

---

## 🚀 Examples Lengkap

### Example 1: Codebase Archive
```bash
python CodeFusion.py --cli -s ./legacy-code -o archive.txt \
    --timestamp --file-size --zip
```
Archive lengkap dengan metadata dan kompresi.

### Example 2: Training Data
```bash
python CodeFusion.py --cli -s ./ml-project -o training.txt \
    -e py \
    --exclude-comments \
    --exclude-line-comments \
    --deduplicate \
    --exclude-folders "tests,examples,docs"
```
Clean training data tanpa comments dan tests.

### Example 3: API Documentation
```bash
python CodeFusion.py --cli -s ./api -o api-docs.md \
    --format markdown \
    --syntax-highlight \
    --line-numbers \
    -e py,js
```
Beautiful API documentation.

### Example 4: RAG Dataset
```bash
python CodeFusion.py --cli -s ./knowledge-base -o rag-dataset.json \
    --format json \
    --smart-chunk \
    --deduplicate \
    --exclude-comments \
    -w 8
```
Optimized dataset untuk RAG applications.

### Example 5: Quick Preview
```bash
python CodeFusion.py --cli -s ./project -o preview.txt \
    --dry-run \
    --no-skipped-detail
```
Fast preview tanpa detail yang tidak perlu.

---

## 📊 Performance Tips

### Untuk Small Projects (< 100 files)
```bash
python CodeFusion.py --cli -s . -o out.txt -w 4
```
Default 4 workers sudah cukup.

### Untuk Medium Projects (100-1000 files)
```bash
python CodeFusion.py --cli -s . -o out.txt -w 8
```
8 workers optimal untuk kebanyakan systems.

### Untuk Large Projects (> 1000 files)
```bash
python CodeFusion.py --cli -s . -o out.txt -w 16 --no-skipped-detail
```
16 workers + skip detail untuk kecepatan maksimal.

---

## 🎓 Best Practices

### ✅ DO
- Gunakan `--dry-run` dulu sebelum proses
- Pilih format yang sesuai (JSON untuk RAG, MD untuk docs)
- Enable `--deduplicate` untuk save space
- Gunakan `--smart-chunk` untuk large files
- Adjust workers sesuai CPU cores

### ❌ DON'T
- Jangan skip dry run untuk project besar
- Jangan gunakan terlalu banyak workers (bisa slow down system)
- Jangan lupa exclude folders yang tidak perlu
- Jangan process binary files (images, executables)

---

## 🔍 Troubleshooting

### Problem: "No files found"
**Solution:** Check source directory dan extension filter
```bash
# Verify directory exists
ls ./myproject

# Try without extension filter
python CodeFusion.py --cli -s ./myproject -o out.txt
```

### Problem: "Permission denied"
**Solution:** Check write permissions
```bash
# Write to current directory
python CodeFusion.py --cli -s ./project -o ./output.txt
```

### Problem: "Out of memory"
**Solution:** Reduce workers atau process smaller batches
```bash
# Use fewer workers
python CodeFusion.py --cli -s . -o out.txt -w 2

# Or process subdirectories separately
python CodeFusion.py --cli -s ./src/part1 -o out1.txt
python CodeFusion.py --cli -s ./src/part2 -o out2.txt
```

### Problem: "Slow processing"
**Solution:** Optimize settings
```bash
# Increase workers
python CodeFusion.py --cli -s . -o out.txt -w 16

# Skip skipped detail
python CodeFusion.py --cli -s . -o out.txt --no-skipped-detail

# Exclude more folders
python CodeFusion.py --cli -s . -o out.txt --exclude-folders ".git,node_modules,venv,test,docs,examples"
```

---

## 📚 Additional Resources

- **Full Documentation:** `IMPROVEMENTS.md`
- **Original README:** `README.md`
- **Examples:** See examples in this file
- **Help:** `python CodeFusion.py --cli --help`

---

## 🎉 Selamat Menggunakan!

AMZ-CodeFusion sekarang 3-4x lebih cepat dengan banyak fitur baru!

**Happy coding! 🚀**

---

*Versi: 2.0 | Updated: 2026-08-29*
