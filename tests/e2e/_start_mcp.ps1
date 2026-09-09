$env:Path = "C:\Users\novad\Desktop\Archive\atlas\target\debug;C:\Users\novad\.cargo\bin;$env:Path"
Set-Location "C:\Users\novad\Desktop\Archive\atlas\line"
go run ./cmd/atlas-mcp --http :8090 --atlas-bin "C:\Users\novad\Desktop\Archive\atlas\target\debug\atlas.exe"
