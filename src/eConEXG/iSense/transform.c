#include <stdio.h>
struct Witharray
{
	double data[136];
};

struct Witharray function(unsigned char *datain)
{
	int temp, head, k = 0, loc = 0;
	struct Witharray test1;
	for (int i = 0; i < 153; i += 1)
	{
		head = i * 3;
		temp = (datain[head] << 16) | (datain[head + 1] << 8) | datain[head + 2];
		(temp & 0x00800000) ? (temp |= 0xFF000000) : (temp &= 0x00FFFFFF);
		if (i % 9)
		{
			test1.data[k++] = temp * 0.02235174;
		}
	}
	return test1;
}