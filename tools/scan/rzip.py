"""Read single files from a remote zip with HTTP range requests: rzip.py <url> list | <url> get <outdir> <n> [n ...]"""
import io
import os
import sys
import urllib.request
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import slusne  # noqa: E402


class RangeFile(io.RawIOBase):
    def __init__(self, url):
        self.url, self.pos = url, 0
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
        self.size = int(slusne.urlopen(req, "stranka", timeout=60).headers["Content-Length"])

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else self.pos + off if whence == 1 else self.size + off
        return self.pos

    def read(self, n=-1):
        if n < 0:
            n = self.size - self.pos
        if n == 0 or self.pos >= self.size:
            return b""
        end = min(self.pos + n, self.size) - 1
        req = urllib.request.Request(self.url, headers={"User-Agent": "Mozilla/5.0", "Range": f"bytes={self.pos}-{end}"})
        data = slusne.urlopen(req, "obrazek", timeout=120).read()
        self.pos += len(data)
        return data

    def readinto(self, b):
        d = self.read(len(b))
        b[:len(d)] = d
        return len(d)


if __name__ == "__main__":
    url, cmd = sys.argv[1], sys.argv[2]
    z = zipfile.ZipFile(io.BufferedReader(RangeFile(url), buffer_size=1 << 16))
    names = sorted(z.namelist())
    if cmd == "list":
        print(len(names), names[0], names[-1])
    else:
        out = sys.argv[3]
        os.makedirs(out, exist_ok=True)
        for a in sys.argv[4:]:
            lo, hi = (map(int, a.split("-")) if "-" in a else (int(a), int(a)))
            for k in range(lo, hi + 1):
                name = names[k - 1]
                with open(os.path.join(out, f"{k:04d}.jpg"), "wb") as f:
                    f.write(z.read(name))
                print(k, name)
