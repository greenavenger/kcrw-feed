# How to acquire golden files

## Sitemaps
```shell
wget -S 'https://www.kcrw.com/sitemap.xml.gz'
wget -S 'https://www.kcrw.com/sitemap-shows/music/sitemap-1.xml.gz'
wget -S 'https://www.kcrw.com/sitemap-shows/music/sitemap-2.xml.gz'
```

## Show pages
```shell
wget -S 'https://www.kcrw.com/music/shows/henry-rollins'
```

## Episode pages
```shell
wget -S 'https://www.kcrw.com/music/shows/dan-wilcox/dan-wilcoxs-playlist-november-28-2020'
```

## Media JSON
```shell
wget -S 'https://www.kcrw.com/music/shows/henry-rollins/kcrw-broadcast-822/player.json'
for i in $(seq 825 -1 817) ; do { mkdir kcrw-broadcast-${i} && wget -S -O kcrw-broadcast-${i}/player.json "https://www.kcrw.com/music/shows/henry-rollins/kcrw-broadcast-${i}/player.json" ; }; done
```
