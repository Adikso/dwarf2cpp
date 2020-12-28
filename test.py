import subprocess

pipe = subprocess.Popen(["perl", "gstlfilt.pl"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
x = pipe.communicate(b'std::map<const Effect*, int, std::less<const Effect*>, std::allocator<std::pair<const Effect* const, int> > >')
print(x[0].decode('utf-8'))
