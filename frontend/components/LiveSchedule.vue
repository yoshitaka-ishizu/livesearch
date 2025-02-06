<template>
  <div>
    <h2 class="text-xl font-bold mb-4">{{ artist }}のスケジュール</h2>
    
    <div v-if="isLoading" class="text-center py-8">
      <USpinner />
    </div>
    
    <div v-else-if="sortedSchedules.length === 0" class="text-center py-8 text-gray-600">
      スケジュールが見つかりませんでした
    </div>
    
    <div v-else class="space-y-4">
      <div v-for="schedule in sortedSchedules" 
           :key="`${schedule.date}-${schedule.venue}`"
           class="bg-white rounded-lg shadow p-4">
        <div class="flex items-start justify-between">
          <div>
            <div class="font-medium">{{ formatDate(schedule.date) }}</div>
            <div class="text-gray-600">{{ schedule.venue }}</div>
            <div v-if="schedule.title" class="text-sm text-gray-500 mt-1">
              {{ schedule.title }}
            </div>
          </div>
          <NuxtLink
          :to="schedule.url"
          target="_blank"
        >
          <UButton
            size="sm"
            variant="outline"
          >
            詳細を見る
          </UButton>
        </NuxtLink>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
interface Schedule {
  date: string
  day: string
  note: string
  artist: string
  venue: string
  title: string
  url: string
}

const props = defineProps<{
  artist: string
}>()

const { getScheduleByArtist } = useEvents()
const schedules = ref<Schedule[]>([])
const isLoading = ref(false)

// スケジュールを日付順にソート（現在日以降のみ）
const sortedSchedules = computed(() => {
  const today = new Date()
  today.setHours(0, 0, 0, 0)  // 今日の0時0分を基準にする

  return [...schedules.value]
    .filter(schedule => {
      const scheduleDate = new Date(schedule.date)
      return scheduleDate >= today
    })
    .sort((a, b) => 
      new Date(a.date).getTime() - new Date(b.date).getTime()
    )
})

// 日付のフォーマット
const formatDate = (dateString: string) => {
  const date = new Date(dateString)
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const weekday = ['日', '月', '火', '水', '木', '金', '土'][date.getDay()]
  return `${year}/${month}/${day}(${weekday})`
}

// アーティストのスケジュール取得
watch(() => props.artist, async (newArtist) => {
  if (newArtist) {
    isLoading.value = true
    try {
      schedules.value = await getScheduleByArtist(newArtist)
    } catch (error) {
      console.error('Failed to fetch schedules:', error)
    } finally {
      isLoading.value = false
    }
  }
}, { immediate: true })
</script>