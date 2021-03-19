# DWARF2CPP

Tool for generating CPP class headers from DWARF debugging format. This program was made for my BSc Thesis.

### Usage
```
python extract.py someFile
```

### Results
Differences between original source code and generated one from DWARF.

```diff
 namespace unknown {
     struct Something {
         int xd;
     };
 };
 
 class Human {
 public:
+    ~Human();   
+    Human(Human arg0);  
+    Human(Human const & arg0);  
+    Human();
     int shared;
     virtual void aaa();
 };

 class Student : Human {
 public:
     enum State {	
         ATTENDING = 0,	
         NOTATTENDING = 1,	
     };

     int tablica[5];
     unknown::Something namespaced;
     char const * firstName;
     char * lastName;
     static int const albumNumber = 123;
-    constexpr static float const skewingFactor = 12.3456f;
+    static float const skewingFactor = 12.3456f;
     int ***** const ** const ** complex;
     union {
         int a12;
         char b;
         long int c;
         union {
             char d;
             char e;
             char f;
         };
     };
     Student(int albumNumber);
     static int * const & static_method(long int some, char *& other);
     int volatile * test(long some, char other);
     void test2();
 private:
     long int pesel;
 };
```