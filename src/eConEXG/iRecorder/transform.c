#include <stdio.h>
struct WithArray
{
	double data[16];
};

struct WithArray function(unsigned char *dataIn)
{
	int temp, head, k = 0, loc = 0;
	struct WithArray test1;
	for (int i = 0; i < 16; i += 1)
	{
		head = i * 3;
		temp = (dataIn[head] << 16) | (dataIn[head + 1] << 8) | dataIn[head + 2];
		(temp & 0x00800000) ? (temp |= 0xFF000000) : (temp &= 0x00FFFFFF);
		test1.data[k++] = temp * 0.02235174;
	}
	return test1;
}