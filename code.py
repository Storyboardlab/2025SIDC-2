the contents of the graph should be filled with the number of empty slots that are left for each day and position.

How you do it is by doing "total slots" - "filled slots"
so for example if the total slots is 3
and filled slots is 1
the number in the graph should be 2
because 3-1 = 2

I will explain again but the total slots is the number that is in the header

1. Allocation Ranges
Use these fixed row numbers per category:
- format: 역할 Rows
so for example) If it's 심사위원 영어 13
심사위원 영어 통역 allocations will be in row 13

✅ For dates 7/10–7/12:
심사위원 영어 13
심사위원 중국어 15:16
심사위원 일본어 18
참가자 영어 20:21
참가자 중국어 23:24
참가자 일본어 26
✅ For dates 7/13–7/19:
심사위원 영어 37:41
심사위원 중국어 43:48
심사위원 일본어 50:52
참가자 영어 54:55
참가자 중국어 57:58
참가자 일본어 60
✅ For dates 7/20–7/22:
심사위원 영어 71:73
심사위원 중국어 75
심사위원 일본어 77
참가자 영어 79:80
참가자 중국어 82:83

2. Header
2.1 Is always right above the allocation range
ex) for rows 82:83 the range is "참가자 중국어"
the headers for 중국어 참가자 통역 will always be in row 81
- so since B81 is inside the range of 7/20(일)
B81 is the header for 중국어 참가자 통역 on 7/20(일)
hence, that's why the data in B81 is "[참가자] 중국어 2"

2.2 format: [역할] 언어 필요인원
* always refer to the total Quota by accessing the number inside the header!!
ex) [심사위원] 영어 3
means the section that corresponds to the header is for 심사위원 영어 통역, and there are a total of 3 spots
ex) [참가자] 중국어 1
means the section that corresponds to the header is for 참가자 중국어통역, and there are a total of 1 spots

3. 심사위원 통역
- Header format: [심사위원] language number
* reminder) If header is present, the number at the end = total slots.
ex) if cell F49 reads "[심사위원] 일본어 1" cuz it's right above allocation range "심사위원 일본어 50:52" it allocates to "심사위원 일본어 통역". and for F50:52, 2 of them will be empty and 1 will be filled with data. Let me explain
- If header cell is missing/blank, mark as N/A. There is no quota for that day/role.

Rows below may contain 3 types of data:
- [name of 심사위원] name of interpreter → filled slot
- [name of 심사위원] blank → empty slot
- blank → meaningless, ignore

and remember that "[name of 심사위원] name of interpreter → filled slot, [name of 심사위원] blank → empty slot" these two types are are mixed randomly mixed in the allocation range.
ex) F42:F48
==== start
[심사위원] 중국어 4
blank
blank
[가오옌진쯔] 김주연
[티안] 상지기
[장샤오메이] 박지현
[우지에]
==== end
You see what I mean by randomly mixed?

4. 참가자 통역
- Header format example: [참가자] 언어 2

Rows below contain only interpreter names (no 심사위원 names).
- Any non-empty cell = filled quota
- blank = empty quota
- Same logic: if header is missing/blank, mark as N/A.

5. apply @st.cache_resource(ttl=60) as done in the original function
