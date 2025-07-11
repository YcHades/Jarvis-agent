docker run -it --rm -p 48081:48081 -v $(pwd):/gs_jarvis -w /gs_jarvis jarvis_backend:v0 python3 serve.py
