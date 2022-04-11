create:
	singularity build --fakeroot check.sif check.def
run:
	./check.sif
