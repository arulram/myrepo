# Quiz: Cats with Hats
# https://gist.github.com/mjhea0/113a48238b65a454f0b5
# The first round, you stop at every cat, placing a hat on each one

list_of_cats = ['hat']*100

# The second round, you only stop at every second cat (#2, #4, #6, #8, etc.).
# The third round, you only stop at every third cat (#3, #6, #9, #12, etc.).
# You continue this process until you've made 100 rounds around the cats (e.g., you only visit the 100th cat).

for round in range(100):
  if round > 0:
    for index, cat in enumerate(list_of_cats):
      if (index+1)%(round+1) == 0:
        if cat == 'hat':
          list_of_cats[index] = None
        else:
          list_of_cats[index]  = 'hat'

for index, cat in enumerate(list_of_cats):
  if cat <> None:
    print 'Cat #'+ str(index+1), 'has a hat'
