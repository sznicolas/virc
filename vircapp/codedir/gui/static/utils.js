var ticker_stats = {}; //received by sse tickerhandler(), used in fill_ticker_details()
var tickerbg = "#2f485a"; //TODO: automaite get bg color to store it

// sse alerts
function flashhandler(event) {
	html = "<div class='alert alert-" + event.type +
		" alert-dismissible' role='alert' data-dismiss='alert' data-toggle='tooltip' title='Click to close'>" +
		event.data + "</div>";
	$(html).prependTo('#flash');
}

// new sse alerts
function messagehandler(event) {
	 var obj = JSON.parse(event.data);
	html = "<div class='alert alert-" + obj.level +
		" alert-dismissible' role='alert' data-dismiss='alert' data-toggle='tooltip' title='Click to close'>" +
		obj.message + "</div>";
	$(html).prependTo('#flash');
}

// updates data in the ticker panel
function tickerhandler(event) {
	//data = event.data; 
	data = JSON.parse(event.data);
	ticker_stats[data.ticker.pair] = data;

	pticker = '#panel-ticker-' + data.ticker.pair;
	ptprice = pticker + " .panel-ticker-price";
	ptoc    = pticker + " .panel-ticker-oc";
	ptlc    = pticker + " .panel-ticker-lc"; // last change mvt
	oldprice = $(ptprice).text();
	if (oldprice < data.ticker.price) {
		hgstyle = {"background-color": "darkGreen"};
		bgcol = "darkGreen";
		$(ptlc).removeClass('fas fa-arrow-down fa-arrow-up').addClass('fas fa-arrow-up') ;
	} else {
		hgstyle = {"background-color": "darkRed"};
		bgcol = "darkRed";
		$(ptlc).removeClass('fas fa-arrow-down fa-arrow-up').addClass('fas fa-arrow-down') ;
	}
	nstyle = {"background-color": "#2f485a"};
	$(pticker).css("background-color", bgcol);
	$(pticker).fadeOut("slow");
	$(ptprice).text(data.ticker.price);
	$(pticker + " .panel-ticker-oc").text(Number((data.ticker.oc).toFixed(2)) + "% "); 
	if ( data.ticker.oc > 0){
		$(ptoc).css("color", "lawnGreen");
	} else if (data.ticker.oc < 0) {
		$(ptoc).css("color", "red");
	}
	if ($("#ticker-detail-pair").text() == data.ticker.pair){
		fill_ticker_details(data.ticker.pair);
	}
	$(pticker).fadeIn("fast")
	setTimeout(function() { $(pticker).css(nstyle) ; }, 2000);
}

// opens the detailled ticker panel
function open_ticker_details(pair) {
	$("#ticker-panel").addClass("ticker-panel-open");
	$("#ticker-panel").removeClass("ticker-panel-mini");
	$("#ticker-details").removeClass("d-none");
	fill_ticker_details(pair);
}

function fill_ticker_details(pair){
	if (typeof(ticker_stats[pair]) === "undefined") {
		close_ticker_details() ;
		return ; 
	}
	var stats = ticker_stats[pair];
	var bgstyle;
	$("#ticker-detail-tbody").empty();
	$("#ticker-detail-pair").text(stats.ticker.pair);
	for ( k in stats) { 
		if ( ! k.startsWith("mob_"))   { continue; }
		if (stats[k].oc > 0) {
				bgstyle = "background-color: darkGreen;";
		} else if (stats[k].oc < 0) {
				bgstyle = "background-color: darkRed;";
		}
		if ( stats[k].vol >= 10) {
				volume = Math.round(stats[k].vol);
		} else {
				volume = stats[k].vol.toFixed(2);
		}
		if (stats[k].range < 1){
				range = Math.round(stats[k].range.toFixed(4) * 100) / 100 ;
		} else {
				range = Math.round(stats[k].range.toFixed(1) * 100) / 100 ;
		}
		html = "<tr style='" + bgstyle + "'><th>" + stats[k].title +
				"</th><td onclick='fill_buy_low(this)'>" + stats[k].low +
				"</td><td onclick='fill_sell_high(this)'>" + stats[k].high + "</td><td>" + 
				volume + "</td><td>" + range +
				"</td><td>" + Math.round(stats[k].oc.toFixed(2) * 100) / 100 + "%</td></tr>";
		$(html).appendTo('#ticker-detail-tbody');
	}
}

function close_ticker_details(){
	$("#ticker-panel").removeClass("ticker-panel-open");
	$("#ticker-panel").addClass("ticker-panel-mini");
	$("#ticker-details").addClass("d-none");
	$("#ticker-detail-pair").text("");
}

function fill_buy_low(obj){
		$('#f_buy_at').val($(obj).text());
		$('#f_buy_at').trigger("change");
}

function fill_sell_high(obj){
		$('#f_sell_at').val($(obj).text());
		$('#f_sell_at').trigger("change");
}

$(window).on('beforeunload', function(){
   		flashsse.close();
		vircpubsse.close();
		tickersse.close();
});

// Confirm with 'confirmation' class
$('.confirmation').on('click', function () {
	return confirm('Are you sure?');
});
