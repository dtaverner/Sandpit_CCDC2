# Creation of a new drug-like subset of the Cambridge Structural Database

This is a group project between Naomi, Dani, Gurleen, and Zeynep as part of the Sandpit Team Project within the ILESLA DPhil at the University of Oxford, in collaboration with the Cambridge Crystallographic Data Centre (CCDC).

## Description

The aim of this project is to provide a comprehensive dataset of ligand-bound crystal structures that are most drug-like. This will provide a thorough starting point in the design of novel drugs as the synthesisability requirement of designed small molecules is already met and with structural biology being critical to the drug discovery process, this dataset will help to overcome this financially and temporally expensive aspect. Overall, this dataset will enable the acceleration of hit-to-lead discovery, lessening of costs, and reduction of drug attrition rates. 

This first part of this code extracts the entire Cambridge Structural Database (CSD) of 1,413,222 entries, filters using Lipinski's Rule of 5, and outputs a subset of predicted drug-like molecules.

## Getting Started

### Dependencies

This code has been written for Python. 

Prior to running the code, a licence to use the CSD must be obtained. Contact your institution or the CCDC here https://www.ccdc.cam.ac.uk/ .

### Installing

In order to handle this dataset, a Python API must be installed in a relevant environment using conda. 

Install the following packages(libraries): io(ccdc), Path(pathlib), Chem(rdkit), pandas, matplotlib.pyplot, venn(venn), upsetplot

### Executing program

* How to run the program
* Step-by-step bullets
```
code blocks for commands

```
## Contributors

This project was carried out by Zeynep Baykam, Naomi Costello, Gurleen Kaur, and Dani Taverner at the University of Oxford. Assistance and guidance was provided by Alexander Hasson at the Oxford Protein Informatics Group and Jasmeen Tatani at the Department of Atmospheric, Oceanic, and Planetary Physics, University of Oxford. Project proposed and supervised by Diana Kondinskaia and Bojana Popovic at the CCDC.

## Contact Information

Zeynep Baykam- zeynep.baykam@gtc.ox.ac.uk 

Naomi Costello- naomi.costello@linacre.ox.ac.uk 

Gurleen Kaur- gurleen.kaur@lincoln.ox.ac.uk 

Dani Taverner- daniela.taverner@seh.ox.ac.uk 
